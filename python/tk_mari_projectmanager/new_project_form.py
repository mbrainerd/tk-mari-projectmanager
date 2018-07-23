# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
UI for creating a new project
"""

import sgtk
from sgtk.platform.qt import QtGui, QtCore

# import the task_manager module from shotgunutils framework
task_manager = sgtk.platform.import_framework(
    "tk-framework-shotgunutils", "task_manager")

# import the shotgun_globals module from shotgunutils framework
shotgun_globals = sgtk.platform.import_framework(
    "tk-framework-shotgunutils", "shotgun_globals")

logger = sgtk.platform.get_logger(__name__)


class NewProjectForm(QtGui.QWidget):
    """
    The main UI used when creating a new Mari project
    """

    # define signals that this form exposes:
    #
    # emitted when the 'Create Project' button is clicked
    create_project = QtCore.Signal(QtGui.QWidget)
    # emitted when the 'Add Publish' button is clicked
    browse_publishes = QtCore.Signal(QtGui.QWidget)
    # emitted when the user requests to remove publishes from the publish list
    remove_publishes = QtCore.Signal(QtGui.QWidget, list)

    def __init__(self, app, init_proc, preview_updater, parent=None):
        """
        Construction

        :param app:             The current app
        :param init_proc:       Called at the end of construction to allow the calling
                                code to hook up any signals, etc.
        :param preview_updater: A background worker that can be used to update the
                                project name preview
        :param parent:          The parent QWidget
        """
        QtGui.QWidget.__init__(self, parent)

        self.__preview_updater = preview_updater
        if self.__preview_updater:
            self.__preview_updater.work_done.connect(self._preview_info_updated)

        # store the current app
        self.__app = app

        # set up the UI
        from .ui.new_project_form import Ui_NewProjectForm
        self.__ui = Ui_NewProjectForm()
        self.__ui.setupUi(self)

        # create a background task manager for each of our components to use
        self.__task_manager = task_manager.BackgroundTaskManager(self)

        # set up the context selected
        self.__ui.context_widget.set_up(self.__task_manager)

        self.__ui.context_widget.set_task_tooltip(
            "<p>The task that the new project will be associated with. The menu button "
            "to the right will provide suggestions for Tasks, including any Tasks "
            "assigned to you, recently used Tasks, and Tasks related to the Link "
            "entity populated in the field below.</p>"
        )
        self.__ui.context_widget.set_link_tooltip(
            "<p>The entity that the new project will be associated with. By selecting a "
            "Task in the field above, the Link field will automatically be populated. "
            "The Task menu above will display any tasks associated with "
            "the entity populated in this field.</p>"
        )

        # you can set a context using the `set_context()` method. Here we set it
        # to the current bundle's context
        self.__ui.context_widget.set_context(self.__app.context)

        # connect the signal emitted by the selector widget when a context is
        # selected. The connected callable should accept a context object.
        self.__ui.context_widget.context_changed.connect(self._on_item_context_change)

        self.__ui.create_btn.clicked.connect(self._on_create_clicked)
        self.__ui.add_publish_btn.clicked.connect(self._on_add_publish_clicked)
        self.__ui.name_edit.textEdited.connect(self._on_name_edited)

        self.__ui.publish_list.set_app(app)
        self.__ui.publish_list.remove_publishes.connect(self._on_remove_selected_publishes)

        # Fix line colours to match 75% of the text colour.  If we don't do this they are
        # extremely bright compared to all other widgets!  This also seems to be the only
        # way to override the default style sheet?!
        clr = QtGui.QApplication.palette().text().color()
        clr_str = "rgb(%d,%d,%d)" % (clr.red() * 0.75, clr.green() * 0.75, clr.blue() * 0.75)
        self.__ui.name_line.setStyleSheet("#name_line{color: %s;}" % clr_str)
        self.__ui.publishes_line.setStyleSheet("#publishes_line{color: %s;}" % clr_str)

        # initialise the UI:
        self.update_publishes()
        init_proc(self)

        # refresh the UI
        self.refresh()

    @property
    def project_name(self):
        """
        Access the entered project name
        :returns:    The project name the user entered
        """
        return self.__ui.name_edit.text()

    def refresh(self):
        """
        Refresh the UI after a context change.
        """
        default_name = self.__app.get_setting("default_project_name")
        self.__ui.name_edit.setText(default_name)

        # If specified, restrict what entries should show up in the list of links when using
        # the auto completer.
        link_entity_types = self.__app.get_setting("link_entity_types")
        if link_entity_types:
            self.__ui.context_widget.restrict_entity_types(link_entity_types)
        else:
            # Else, we only show entity types that are allowed for the Task.entity field.
            self.__ui.context_widget.restrict_entity_types_by_link("Task", "entity")

        # Enable project settings if we're in a Task context
        self.__ui.context_warning_label.setText("")
        if self.__app.context.task:
            # Also check that the selected entity matches one of the allowed entity types
            if link_entity_types:
                ent_type = self.__app.context.entity["type"]
                if ent_type in link_entity_types:
                    self.__ui.project_groupbox.setEnabled(True)
                else:
                    msg = "Invalid: Selected Link is of type '%s', but must be one of: %s" % (ent_type, link_entity_types)
                    warning = "<p style='color:rgb(226, 146, 0)'>%s</p>" % msg
                    self.__ui.context_warning_label.setText(warning)
                    self.__ui.project_groupbox.setEnabled(False)
            else:
                self.__ui.project_groupbox.setEnabled(True)
        else:
            self.__ui.project_groupbox.setEnabled(False)

        # update the name preview:
        if self.__preview_updater:
            self.__preview_updater.do(default_name)

    def update_publishes(self, sg_publish_data=None):
        """
        Update the list of publishes

        :param sg_publish_data: The list of publishes to present.  This is a list of
                                Shotgun entity dictionaries.
        """
        # clear the existing publishes from the list:
        self.__ui.publish_list.clear()
        if not sg_publish_data:
            # display the error message in the list and siable the create button:
            self.__ui.publish_list.set_message("<i>You must add at least one publish before "
                                               "you can create the new project...</i>")
            self.__ui.create_btn.setEnabled(False)
        else:
            # load the publishes into the list and enable the create button:
            self.__ui.publish_list.load(sg_publish_data)
            self.__ui.create_btn.setEnabled(True)

    def closeEvent(self, event):
        """
        Called when the widget is closed so that any cleanup can be
        done. Overrides QWidget.clostEvent.

        :param event:    The close event.
        """
        # make sure the publish list BrowserWidget is
        # cleaned up properly
        self.__ui.publish_list.destroy()

        # disconnect the preview updater:
        if self.__preview_updater:
            self.__preview_updater.work_done.disconnect(self._preview_info_updated)

        # register the data fetcher with the global schema manager
        shotgun_globals.unregister_bg_task_manager(self.__task_manager)

        try:
            # shut down main threadpool
            self.__task_manager.shut_down()
        except Exception:
            logger.exception("Error running closeEvent()")

        # ensure the context widget's recent contexts are saved
        self.__ui.context_widget.save_recent_contexts()

        # reset the context if it was changed
        if self.__app.context != self.__app.engine.context:
            self.__app.change_context(self.__app.engine.context)

        # return result from base implementation
        return QtGui.QWidget.closeEvent(self, event)

    def _on_item_context_change(self, context):
        """
        Fires when a new context is selected for the current item
        """
        # typically the context would be set by some external process. for now,
        # we'll just re-set the context based on what was selected. this will
        # have the added effect of populating the "recent" items in the drop
        # down list
        self.__ui.context_widget.set_context(context)

        # If the context has changed, refresh the application
        if context != self.__app.context:
            self.__app.change_context(context)

    def _on_create_clicked(self):
        """
        Called when the user clicks the create button
        """
        self.create_project.emit(self)

    def _on_add_publish_clicked(self):
        """
        Called when the user clicks the add publish button
        """
        self.browse_publishes.emit(self)

    def _on_name_edited(self, txt):
        """
        Called when the user edits the name
        :param txt:    The current text entered into the edit control
        """
        # update the name preview:
        if self.__preview_updater:
            self.__preview_updater.do(self.project_name)

    def _on_remove_selected_publishes(self, publish_ids):
        """
        Called when the user requests to remove some publishes from the list

        :param publish_ids:    The list of publish ids to be removed
        """
        self.remove_publishes.emit(self, publish_ids)

    def _preview_info_updated(self, name, result):
        """
        Called when the worker thread has finished generating the
        new project name

        :param name:    The name entered in to the name edit control
        :param result:  The result returned by the worker thread.  This is a dictionary
                        containing the "project_name" and/or the error "message".
        """
        project_name = result.get("project_name")
        if project_name:
            # updat the preview with the project name:
            self.__ui.name_preview_label.setText("<b>%s</b>" % project_name)
        else:
            # update the preview with the error message:
            message = result.get("message", "")
            warning = "<p style='color:rgb(226, 146, 0)'>%s</p>" % message
            self.__ui.name_preview_label.setText(warning)
