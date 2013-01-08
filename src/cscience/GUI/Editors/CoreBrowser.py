"""
CoreBrowser.py

* Copyright (c) 2006-2015, University of Colorado.
* All rights reserved.
*
* Redistribution and use in source and binary forms, with or without
* modification, are permitted provided that the following conditions are met:
*     * Redistributions of source code must retain the above copyright
*       notice, this list of conditions and the following disclaimer.
*     * Redistributions in binary form must reproduce the above copyright
*       notice, this list of conditions and the following disclaimer in the
*       documentation and/or other materials provided with the distribution.
*     * Neither the name of the University of Colorado nor the
*       names of its contributors may be used to endorse or promote products
*       derived from this software without specific prior written permission.
*
* THIS SOFTWARE IS PROVIDED BY THE UNIVERSITY OF COLORADO ''AS IS'' AND ANY
* EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
* WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
* DISCLAIMED. IN NO EVENT SHALL THE UNIVERSITY OF COLORADO BE LIABLE FOR ANY
* DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
* (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
* LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
* ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
* (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
* SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import wx
import wx.grid
import wx.lib.itemspicker
import wx.lib.delayedresult
from wx.lib.agw import ribbon

from cscience.GUI.Util import ribbonpatch
ribbon.RibbonPanel = ribbonpatch.RibbonPanelSizer

import os
import csv

from cscience import datastore
from cscience.GUI import events
from cscience.GUI.Editors import AttEditor, MilieuBrowser, ComputationPlanBrowser, \
            FilterEditor, TemplateEditor, ViewEditor, MemoryFrame
from cscience.GUI.Util import SampleBrowserView, Plot, grid
from cscience.framework import Core, Sample

import calvin.argue
        

class SampleGridTable(grid.UpdatingTable):
    def __init__(self, *args, **kwargs):
        self._samples = []
        #The samples shown get updated when the view is updated (since text
        #search is redone), so this doesn't need to be a property to re-draw.
        self.view = []
        super(SampleGridTable, self).__init__(*args, **kwargs)

    @property
    def samples(self):
        return self._samples
    @samples.setter
    def samples(self, value):
        self._samples = value
        self.reset_view()
        
    def GetNumberRows(self):
        return len(self.samples) or 1
    def GetNumberCols(self):
        return (len(self.view) or 2) - 1
    def GetValue(self, row, col):
        if not self.view:
            return "The current view has no attributes defined for it."
        elif not self.samples:
            return ''
        return str(self.samples[row][self.view[col+1]])
    def GetRowLabelValue(self, row):
        if not self.samples:
            return ''
        return self.samples[row]['depth']
    def GetColLabelValue(self, col):
        if not self.view:
            return "Invalid View"
        return self.view[col+1].replace(' ', '\n')

class CoreBrowser(MemoryFrame):
    
    framename = 'samplebrowser'
    
    def __init__(self):
        super(CoreBrowser, self).__init__(parent=None, id=wx.ID_ANY, 
                                          title='CScience', size=(540, 380))
        #hide the frame until the initial repo is loaded, to prevent flicker.
        self.Show(False)
        self.browser_view = SampleBrowserView()        
        self.core = None
        self.view = None
        self.filter = None
        
        self.CreateStatusBar()
        self.create_menus()
        self.create_widgets()
        
        self.Bind(events.EVT_REPO_CHANGED, self.on_repository_altered)
        self.Bind(wx.EVT_CLOSE, self.quit)

    def create_menus(self):
        menu_bar = wx.MenuBar()

        #Build File menu
        #Note: on a mac, the 'Quit' option is moved for platform nativity automatically
        file_menu = wx.Menu()
        item = file_menu.Append(wx.ID_OPEN, "Switch Repository\tCtrl-O", 
                                     "Switch to a different CScience Repository")
        self.Bind(wx.EVT_MENU, self.change_repository, item)
        file_menu.AppendSeparator()
        item = file_menu.Append(wx.ID_SAVE, "Save Repository\tCtrl-S", 
                                   "Save changes to current CScience Repository")
        self.Bind(wx.EVT_MENU, self.save_repository, item)
        file_menu.AppendSeparator()
        item = file_menu.Append(wx.ID_EXIT, "Quit CScience\tCtrl-Q", 
                                   "Quit CScience")
        self.Bind(wx.EVT_MENU, self.quit, item)
        
        edit_menu = wx.Menu()
        item = edit_menu.Append(wx.ID_COPY, "Copy\tCtrl-C", "Copy selected samples.")
        self.Bind(wx.EVT_MENU, self.OnCopy, item)
        
        tool_menu = wx.Menu()
        def bind_editor(name, edclass, menuname, tooltip):
            menuitem = tool_menu.Append(wx.ID_ANY, menuname, tooltip)
            hid_name = ''.join(('_', name))
            def del_editor(event, *args, **kwargs):
                setattr(self, hid_name, None)
            
            def create_editor():
                editor = getattr(self, hid_name, None)
                if not editor:
                    #TODO: fix this hack!
                    editor = getattr(edclass, edclass.__name__.rpartition('.')[2])(self)
                    self.Bind(wx.EVT_CLOSE, del_editor, editor)
                    setattr(self, hid_name, editor)
                return editor
            
            def raise_editor(event, *args, **kwargs):
                editor = create_editor()
                editor.Show()
                editor.Raise()
            self.Bind(wx.EVT_MENU, raise_editor, menuitem)
            return menuitem
        
        bind_editor('filter_editor', FilterEditor, "Filter Editor\tCtrl-1", 
                "Create and Edit CScience Filters for use in the Sample Browser")
        bind_editor('view_editor', ViewEditor, "View Editor\tCtrl-2", 
                "Edit the list of views that can filter the display of samples in CScience")
        tool_menu.AppendSeparator()
        bind_editor('attribute_editor', AttEditor, "Attribute Editor\tCtrl-3", 
                "Edit the list of attributes that can appear on samples in CScience")
        tool_menu.AppendSeparator()
        bind_editor('template_editor', TemplateEditor, "Template Editor\tCtrl-4", 
                "Edit the list of templates for the CScience Paleobase")
        bind_editor('milieu_browser', MilieuBrowser, "Milieu Browser\tCtrl-5", 
                "Browse and Import Paleobase Entries")
        tool_menu.AppendSeparator()
        bind_editor('cplan_browser', ComputationPlanBrowser, "Computation Plan Browser\tCtrl-6", 
                "Browse Existing Computation Plans and Create New Computation Plans")
         
        help_menu = wx.Menu()
        item = help_menu.Append(wx.ID_ABOUT, "About CScience", "View Credits")
        self.Bind(wx.EVT_MENU, self.show_about, item)
        
        #Disallow save unless there's something to save :)
        file_menu.Enable(wx.ID_SAVE, False)
        #Disable copy when no rows are selected
        edit_menu.Enable(wx.ID_COPY, False)
        
        menu_bar.Append(file_menu, "&File")
        menu_bar.Append(edit_menu, "&Edit")
        menu_bar.Append(tool_menu, "&Tools")
        menu_bar.Append(help_menu, "&Help")
        self.SetMenuBar(menu_bar)
        
    def create_action_buttons(self):  
        #TODO: These would make a lot more sense as menu & toolbar thingies.
        self.button_panel = wx.Panel(self, wx.ID_ANY)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        imp_button = wx.Button(self.button_panel, wx.ID_ANY, "Import Samples...")
        self.Bind(wx.EVT_BUTTON, self.import_samples, imp_button)
        button_sizer.Add(imp_button, border=5, flag=wx.ALL)
        
        calc_button = wx.Button(self.button_panel, wx.ID_APPLY, "Do Calculations...")
        self.Bind(wx.EVT_BUTTON, self.OnDating, calc_button)
        button_sizer.Add(calc_button, border=5, flag=wx.ALL)
        
        calv_button = wx.Button(self.button_panel, wx.ID_ANY, "Analyze Ages...")
        self.Bind(wx.EVT_BUTTON, self.OnRunCalvin, calv_button)
        button_sizer.Add(calv_button, border=5, flag=wx.ALL)
        
        self.del_button = wx.Button(self.button_panel, wx.ID_DELETE, "Delete Sample...")
        self.Bind(wx.EVT_BUTTON, self.OnDeleteSample, self.del_button)
        button_sizer.Add(self.del_button, border=5, flag=wx.ALL)
        self.del_button.Disable()
        
        self.strip_button = wx.Button(self.button_panel, wx.ID_ANY, "Strip Calculated Data...")
        self.Bind(wx.EVT_BUTTON, self.OnStripExperiment, self.strip_button)
        button_sizer.Add(self.strip_button, border=5, flag=wx.ALL)
        self.strip_button.Disable()
        
        exp_button = wx.Button(self.button_panel, wx.ID_ANY, "Export Samples...")
        self.Bind(wx.EVT_BUTTON, self.OnExportView, exp_button)
        button_sizer.Add(exp_button, border=5, flag=wx.ALL)
        
        self.button_panel.SetSizer(button_sizer)      
        return self.button_panel
    
    def create_ribbon(self):
        rib = ribbon.RibbonBar(self, wx.ID_ANY, 
                               agwStyle=ribbon.RIBBON_BAR_FLOW_HORIZONTAL)   
        rap = rib.GetArtProvider()     
        bf = rap.GetFont(ribbon.RIBBON_ART_BUTTON_BAR_LABEL_FONT)
        #default point size is ugly-small; make larger but still wee for betters
        bf.SetPointSize((bf.GetPointSize() * 5) / 4)
        browse = ribbon.RibbonPage(rib, wx.ID_ANY, "Browse Samples")
        core_panel = ribbon.RibbonPanel(browse, wx.ID_ANY, "Select Core",
                            agwStyle=ribbon.RIBBON_PANEL_NO_AUTO_MINIMISE)
        
        self.selected_core = wx.Choice(core_panel, id=wx.ID_ANY, 
                            choices=['No Core Selected'])
        self.selected_core.SetFont(bf)
        self.selected_core.SetSize(self.selected_core.GetMinSize())
        sz = wx.BoxSizer(wx.HORIZONTAL)
    
        sz.Add(self.selected_core, flag=wx.CENTER)
        core_panel.SetSizer(sz)
        
        view_panel = ribbon.RibbonPanel(browse, wx.ID_ANY, "Filter View",
                            agwStyle=ribbon.RIBBON_PANEL_NO_AUTO_MINIMISE)
        toolbar = ribbon.RibbonButtonBar(view_panel, wx.ID_ANY)
        self.selected_view = toolbar.AddDropdownButton(wx.NewId(), 'View Attributes', 
                    wx.ArtProvider.GetBitmap(wx.ART_REPORT_VIEW, wx.ART_TOOLBAR, 
                                             (32, 32)))
        self.selected_filter = toolbar.AddDropdownButton(wx.NewId(), 'Filter Samples',
                    wx.ArtProvider.GetBitmap(wx.ART_FIND, wx.ART_TOOLBAR, 
                                             (32, 32)))
        
        self.search_box = wx.SearchCtrl(view_panel, wx.ID_ANY, size=(150,-1), 
                                                      style=wx.TE_PROCESS_ENTER)
        search_menu = wx.Menu()
        self.exact_box = search_menu.AppendCheckItem(wx.ID_ANY, 'Use Exact Match')
        self.search_box.SetMenu(search_menu)
        #TODO: bind cancel button to evt :)
        self.search_box.ShowCancelButton(True)
        sz = wx.BoxSizer(wx.HORIZONTAL)
        sz.Add(toolbar)
        sz.AddSpacer(10)
        sz.Add(self.search_box, flag=wx.CENTER)
        view_panel.SetSizer(sz)
        
        def on_view_dropdown(event):
            menu = wx.Menu()
            #TODO: sorting? or not needed?
            for view in datastore.views.keys():
                item = menu.AppendRadioItem(wx.ID_ANY, view)
                if self.view and self.view.name == view:
                    item.Check()

            def menu_pick(event):
                item = menu.FindItemById(event.Id)
                self.set_view(item.Label)
                
            menu.Bind(wx.EVT_MENU, menu_pick)
            event.PopupMenu(menu)
            menu.Destroy()
            
        def on_filter_dropdown(event):
            menu = wx.Menu()
            item = menu.AppendRadioItem(wx.ID_ANY, '<No Filter>')
            if not self.filter:
                item.Check()
            for filt in sorted(datastore.filters.keys()):
                item = menu.AppendRadioItem(wx.ID_ANY, filt)
                if self.filter and self.filter.name == filt:
                    item.Check()
                
            def menu_pick(event):
                item = menu.FindItemById(event.Id)
                self.set_filter(item.Label)
            
            menu.Bind(wx.EVT_MENU, menu_pick)
            event.PopupMenu(menu)
            menu.Destroy()
        
        toolbar.Bind(ribbon.EVT_RIBBONBUTTONBAR_DROPDOWN_CLICKED, on_view_dropdown, 
                     id=self.selected_view.id)
        toolbar.Bind(ribbon.EVT_RIBBONBUTTONBAR_DROPDOWN_CLICKED, on_filter_dropdown, 
                     id=self.selected_filter.id)
        self.Bind(wx.EVT_CHOICE, self.select_core, self.selected_core)
        self.Bind(wx.EVT_TEXT, self.update_search, self.search_box)
        self.Bind(wx.EVT_MENU, self.update_search, self.exact_box)
        
        sort_panel = ribbon.RibbonPanel(browse, wx.ID_ANY, "Sort",
                           agwStyle=ribbon.RIBBON_PANEL_NO_AUTO_MINIMISE)
        toolbar = ribbon.RibbonButtonBar(sort_panel, wx.ID_ANY)
        
        """
        self.sselect_prim = wx.ComboBox(self, wx.ID_ANY, choices=["Not Sorted"], 
                                style=wx.CB_DROPDOWN | wx.CB_READONLY | wx.CB_SORT)
        self.sselect_sec = wx.ComboBox(self, wx.ID_ANY, choices=["Not Sorted"], 
                                style=wx.CB_DROPDOWN | wx.CB_READONLY | wx.CB_SORT)
        self.sdir_select = wx.ComboBox(self, wx.ID_ANY, 
                    value=self.browser_view.get_direction(), 
                    choices=["Ascending", "Descending"], 
                    style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.Bind(wx.EVT_COMBOBOX, self.OnChangeSort, self.sselect_prim)
        self.Bind(wx.EVT_COMBOBOX, self.OnChangeSort, self.sselect_sec)
        self.Bind(wx.EVT_COMBOBOX, self.OnSortDirection, self.sdir_select)
        """
        
        return rib
        
    def create_widgets(self):
        #TODO: save & load these values using PersistentControls
        
        rib = self.create_ribbon()
        self.filter_desc = wx.StaticText(self, wx.ID_ANY, "No Filter Selected")
        
        
        
        self.plot_sort = wx.Button(self, wx.ID_ANY, "Plot Sort Attributes...")
        self.Bind(wx.EVT_BUTTON, self.OnPlotSort, self.plot_sort)
        
        
        
        self.grid = grid.LabelSizedGrid(self, wx.ID_ANY)
        self.table = SampleGridTable(self.grid)
        self.grid.SetSelectionMode(wx.grid.Grid.SelectRows)
        self.grid.AutoSize()
        self.grid.EnableEditing(False)
        
        self.create_action_buttons()
        
        rib.Realize()
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(rib, border=5, flag=wx.EXPAND)
        sizer.Add(self.filter_desc)
        
        row_sizer = wx.BoxSizer(wx.HORIZONTAL)
        row_sizer.Add(wx.StaticText(self, wx.ID_ANY, "Sort by"), border=5, flag=wx.ALL)
        row_sizer.Add(self.sselect_prim, border=5, flag=wx.ALL)
        row_sizer.Add(wx.StaticText(self, wx.ID_ANY, "and then by"), border=5, flag=wx.ALL)
        row_sizer.Add(self.sselect_sec, border=5, flag=wx.ALL)
        row_sizer.Add(self.sdir_select, border=5, flag=wx.ALL)
        row_sizer.Add(self.plot_sort, border=5, flag=wx.ALL)
        sizer.Add(row_sizer, flag=wx.EXPAND)
        
        sizer.Add(self.grid, proportion=1, flag=wx.EXPAND)
        
        sizer.Add(self.button_panel)
        self.SetSizer(sizer)

    def show_about(self, event):
        dlg = AboutBox(self)
        dlg.ShowModal()
        dlg.Destroy()
    
    def quit(self, event):
        self.close_repository()
        wx.Exit()
        
    def on_repository_altered(self, event):
        """
        Used to cause the File->Save Repo menu option to be enabled only if
        there is new data to save.
        """
        if 'views' in event.changed:
            view_name = self.browser_view.get_view()
            if view_name not in datastore.views:
                # if current view has been deleted, then switch to "All" view
                self.set_view('All')
            elif event.value and view_name == event.value:
                #if the current view has been updated, display new data as
                #appropriate
                self.set_view(view_name)
        elif 'filters' in event.changed:
            filter_name = self.browser_view.get_filter()
            # if current filter has been deleted, then switch to "None" filter
            if filter_name not in datastore.filters:
                self.set_filter(None)
            elif event.value and filter_name == event.value:
                    #if we changed the currently selected filter, we should
                    #re-filter the current view.
                self.set_filter(filter_name)
        else:
            #TODO: select new core on import, & stuff.
            self.show_new_core()
        datastore.data_modified = True
        self.GetMenuBar().Enable(wx.ID_SAVE, True)
        event.Skip()
        
    def change_repository(self, event):
        self.close_repository()
        
        #Close all other editors, as the repository is changing...
        for window in self.Children:
            if window.IsTopLevel():
                window.Close()
                
        self.open_repository()
        self.SetTitle(' '.join(('CScience:', datastore.data_source)))

    def open_repository(self, repo_dir=None):
        if not repo_dir:
            dialog = wx.DirDialog(None, "Choose a Repository", 
                style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST | wx.DD_CHANGE_DIR)
            if dialog.ShowModal() == wx.ID_OK:
                repo_dir = dialog.GetPath()
                dialog.Destroy()
            else:
                #end the app, if the user doesn't want to open a repo dir
                self.Close()
                return
        elif not os.path.exists(repo_dir):
            raise datastore.RepositoryException('Previously saved repository no longer exists.')
        
        try:
            datastore.set_data_source(repo_dir)
        except Exception as e:
            import traceback
            print repr(e)
            print traceback.format_exc()
            raise datastore.RepositoryException('Error while loading selected repository.')
        else:
            self.selected_core.SetItems(sorted(datastore.cores.keys()) or
                                        ['No Cores -- Import Samples to Begin'])
            self.selected_core.SetSelection(0)
            
            self.show_new_core()
            wx.CallAfter(self.Raise)

    def close_repository(self):
        if datastore.data_modified:
            if wx.MessageBox('You have modified this repository. '
                    'Would you like to save your changes?', "Unsaved Changes", 
                    wx.YES_NO | wx.ICON_EXCLAMATION) == wx.YES:
                self.save_repository(None)
        #just in case, for now
        datastore.data_modified = False
        
    def save_repository(self, event):
        datastore.save_datastore()
        
    def OnCopy(self, event):
        samples = [self.displayed_samples[index] for index in self.grid.SelectedRowset]
        view = datastore.views[self.browser_view.get_view()]        
        #views are guaranteed to give attributes as id, then computation_plan, then
        #remaining atts in order when iterated.
        result = os.linesep.join(['\t'.join([
                    datastore.sample_attributes.format_value(att, sample[att]) 
                    for att in view]) for sample in samples])
        result = os.linesep.join(['\t'.join(view), result])
        
        data = wx.TextDataObject()
        data.SetText(result)
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(data)
            wx.TheClipboard.Close()
            
    def show_new_core(self):
        self.samples = []
        if self.core is not None:
            for vc in self.core.virtualize():
                self.samples.extend(vc)
        self.filter_samples()
        
    def filter_samples(self):
        self.displayed_samples = None
        filter_name = self.browser_view.get_filter()
        try:
            filt = datastore.filters[filter_name]
        except KeyError:
            self.browser_view.set_filter('<No Filter>')
            self.filter_desc.SetLabel('No Filter Selected')
            filtered_samples = self.samples[:]
        else:
            self.filter_desc.SetLabel(filt.description)
            filtered_samples = filter(filt.apply, self.samples)
        self.search_samples(filtered_samples)

    def search_samples(self, samples_to_search=[]):
        value = self.search_box.GetValue()
        if value:
            self.previous_query = value
            view = datastore.views[self.browser_view.get_view()]
            self.displayed_samples = [s for s in samples_to_search if 
                                s.search(value, view, self.exact_box.IsChecked())]
        else:
            self.displayed_samples = samples_to_search
            self.previous_query = ''
        self.display_samples()
        
    def display_samples(self):        
        def sort_none_last(x, y):
            def cp_none(x, y):
                if x is None and y is None:
                    return 0
                elif x is None:
                    return 1
                elif y is None:
                    return -1
                else:
                    return cmp(x, y)
            for a, b in zip(x, y):
                val = cp_none(a, b)
                if val:
                    return val
            return 0
        
        self.displayed_samples.sort(cmp=sort_none_last, 
                            key=lambda s: (s[self.browser_view.get_primary()], 
                                           s[self.browser_view.get_secondary()]), 
                            reverse=self.GetSortDirection())
        
        self.table.view = datastore.views[self.browser_view.get_view()]
        self.table.samples = self.displayed_samples
        
    def update_search(self, event):
        value = self.search_box.GetValue()
        if value and not self.exact_box.IsChecked() and \
           self.displayed_samples and self.previous_query in value:
            self.search_samples(self.displayed_samples)
        else:
            #unless all of the above is true, we may have previously-excluded
            #samples showing up in the search result. Since this is possible,
            #we need to start from the filtered set again, not the displayed set.
            #TODO: can keep a self.filtered_samples around 
            #to save a little work here.
            self.filter_samples()
        
    def OnExportView(self, event):
        
        view_name = self.browser_view.get_view()
        view = datastore.views[view_name]
        # add header labels -- need to use iterator to get computation_plan/id correct
        rows = [att for att in view]
        rows.extend([[sample[att] for att in view] for sample in self.displayed_samples])
        
        wildcard = "CSV Files (*.csv)|*.csv|"     \
                   "All files (*.*)|*.*"

        dlg = wx.FileDialog(self, message="Save view in ...", defaultDir=os.getcwd(), defaultFile="view.csv", wildcard=wildcard, style=wx.SAVE | wx.CHANGE_DIR | wx.OVERWRITE_PROMPT)
        dlg.SetFilterIndex(0)
        
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()        
            tmp = open(path, "wb")
            writer = csv.writer(tmp)
            writer.writerows(rows)
        
            tmp.flush()
            tmp.close()
            
            the_dir = os.path.dirname(path)
            os.chdir(the_dir)
            
        dlg.Destroy()

    def OnPlotSort(self, event):
        graph = Plot(self.displayed_samples, self.browser_view.get_primary(),
                     self.browser_view.get_secondary())
        graph.showFigure()
        

    def import_samples(self, event):
        dialog = wx.FileDialog(None,
                "Please select a CSV File containing Samples to be Imported or Updated:",
                defaultDir=os.getcwd(), wildcard="CSV Files (*.csv)|*.csv|All Files|*.*",
                style=wx.OPEN | wx.DD_CHANGE_DIR)
        result = dialog.ShowModal()
        path = dialog.GetPath()
        #destroy the dialog now so no problems happen on early return
        dialog.Destroy()
        
        if result == wx.ID_OK:
            with open(path, 'rU') as input_file:
                #allow whatever sane csv formats we can manage, here
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(input_file.read(1024))
                dialect.skipinitialspace = True
                input_file.seek(0)
                
                reader = csv.DictReader(input_file, dialect=dialect)
                if not reader.fieldnames:
                    wx.MessageBox("Selected file is empty.", "Operation Cancelled", 
                                  wx.OK | wx.ICON_INFORMATION)
                    return
                #strip extra spaces, since that was apparently a problem before?
                reader.fieldnames = [name.strip() for name in reader.fieldnames]
                   
                if 'depth' not in reader.fieldnames:
                    wx.MessageBox("Selected file is missing the required attribute 'depth'.", 
                                  "Operation Cancelled", wx.OK | wx.ICON_INFORMATION)
                    return
                
                rows = []
                for index, line in enumerate(reader, 1):
                    #do appropriate type conversions...
                    for key, value in line.iteritems():
                        try:
                            line[key] = datastore.sample_attributes.convert_value(key, value)
                        except ValueError:
                            wx.MessageBox("%s on row %i has an incorrect type."
                                "Please update the csv file and try again." % (key, index),
                                "Operation Cancelled", wx.OK | wx.ICON_INFORMATION)
                            return
                    rows.append(line)
                if not rows:
                    wx.MessageBox("Selected file appears to contain no data.", 
                                  "Operation Cancelled", wx.OK | wx.ICON_INFORMATION)
                    return
                
                dialog = DisplayImportedSamples(self, os.path.basename(path), 
                                                reader.fieldnames, rows)
                if dialog.ShowModal() == wx.ID_OK:
                    if dialog.source_name:
                        for item in rows:
                            item['source'] = dialog.source_name
                    cname = dialog.core_name
                    core = datastore.cores.get(cname, None)
                    if core is None:
                        core = Core(cname)               
                        datastore.cores[cname] = core            
                    for item in rows:
                        s = Sample('input', item)
                        core.add(s)
        
                    wx.MessageBox('Core %s imported/updated' % cname, "Import Results",
                                  wx.OK | wx.CENTRE)
                    events.post_change(self, 'samples')
                dialog.Destroy()

    def OnRunCalvin(self, event):
        """
        Runs Calvin on all highlighted samples, or all samples if none are
        highlighted.
        """
        
        if not self.grid.SelectedRowset:
            samples = self.displayed_samples
        else:
            indexes = list(self.grid.SelectedRowset)
            samples = [self.displayed_samples[index] for index in indexes]
        
        calvin.argue.analyzeSamples(samples)
        
    def select_core(self, event):
        try:
            self.core = datastore.cores[self.selected_core.GetStringSelection()]
        except KeyError:
            self.core = None
        self.show_new_core()

    def set_filter(self, filter_name):
        self.browser_view.set_filter(filter_name)
        self.filter_samples()
 
    def set_view(self, view_name):
        try:
            self.view = datastore.views[view_name]
        except KeyError:
            view_name = 'All'
            self.view = datastore.views['All']
        self.browser_view.set_view(view_name)
        
        self.sselect_prim.SetItems(self.view)
        self.sselect_sec.SetItems(self.view)

        previous_primary = self.browser_view.get_primary()
        previous_secondary = self.browser_view.get_secondary()
            
        if previous_primary in self.view:
            self.sselect_prim.SetStringSelection(previous_primary)
        else:
            self.sselect_prim.SetStringSelection("depth")
            self.browser_view.set_primary("depth")
            
        if previous_secondary in self.view:
            self.sselect_sec.SetStringSelection(previous_secondary)
        else:
            self.sselect_sec.SetStringSelection("computation plan")
            self.browser_view.set_secondary("computation plan")
        
        self.filter_samples()

    def GetSortDirection(self):
        # return true for descending, else return false
        # this corresponds to the expected value for the reverse parameter of the sort() method
        if self.browser_view.get_direction() == "Descending":
            return True
        return False

    def OnSortDirection(self, event):
        self.browser_view.set_direction(self.sdir_select.GetStringSelection())
        self.display_samples()

    def OnChangeSort(self, event):
        self.browser_view.set_primary(self.sselect_prim.GetStringSelection())
        self.browser_view.set_secondary(self.sselect_sec.GetStringSelection())
        self.display_samples()

    def OnDating(self, event):
        dlg = ComputationDialog(self, self.core)
        ret = dlg.ShowModal()
        plan = dlg.plan
        # depths = dlg.depths
        dlg.Destroy()
        if ret != wx.ID_OK:
            return
        computation_plan = datastore.computation_plans[plan]
        workflow = datastore.workflows[computation_plan['workflow']]
        vcore = self.core.new_computation(plan)
        aborting = wx.lib.delayedresult.AbortEvent()
        
        self.button_panel.Disable()
        self.plot_sort.Disable()
        
        dialog = WorkflowProgress(self, "Applying Computation '%s'" % plan)
        wx.lib.delayedresult.startWorker(self.OnDatingDone, workflow.execute, 
                                  wargs=(computation_plan, vcore, aborting),
                                  cargs=(plan, self.core, dialog))
        if dialog.ShowModal() != wx.ID_OK:
            aborting.set()
            self.core.strip_experiment(plan)
        dialog.Destroy()

    def OnDatingDone(self, dresult, planname, core, dialog):
        try:
            result = dresult.get()
        except Exception as exc:
            core.strip_experiment(planname)
            print exc
            wx.MessageBox("There was an error running the requested computation."
                          " Please contact support.")
        else:
            dialog.EndModal(wx.ID_OK)
            events.post_change(self, 'samples')
        finally:
            self.button_panel.Enable()
            self.plot_sort.Enable()
        
    def OnStripExperiment(self, event):
        
        indexes = list(self.grid.SelectedRowset)
        samples = [self.displayed_samples[index] for index in indexes]
        
        dialog = wx.MessageDialog(None, 'This operation will strip all performed computations from the selected samples. (Note: Input cannot be deleted.) Are you sure you want to do this?', "Are you sure?", wx.YES_NO | wx.ICON_EXCLAMATION)
        if dialog.ShowModal() == wx.ID_YES:
            for sample in samples:
                for exp in sample.keys():
                    if exp != 'input':
                        del sample[exp]
        
            self.grid.ClearSelection()
            events.post_change(self, 'samples')

    def OnDeleteSample(self, event):
        
        indexes = self.grid.SelectedRowset
        samples = [self.displayed_samples[index] for index in indexes]
        ids = [sample['id'] for sample in samples]
        
        dialog = wx.MessageDialog(None, 'Are you sure that you want to delete the following samples: %s' % (ids), "Are you sure?", wx.YES_NO | wx.ICON_EXCLAMATION)
        if dialog.ShowModal() == wx.ID_YES:
            for s_id in ids:
                del self.core[depth]
            self.grid.ClearSelection()
            events.post_change(self, 'samples')                
                
                
class DisplayImportedSamples(wx.Dialog):
    class CorePanel(wx.Panel):
        def __init__(self, parent, default_name=''):
            super(DisplayImportedSamples.CorePanel, self).__init__(parent, 
                                    style=wx.TAB_TRAVERSAL | wx.BORDER_SIMPLE)
            
            self.new_core = wx.RadioButton(self, wx.ID_ANY, 'Create new core', 
                                       style=wx.RB_GROUP)
            self.existing_core = wx.RadioButton(self, wx.ID_ANY, 'Add to existing core')
            
            self.new_panel = wx.Panel(self, size=(300, -1))
            self.core_name = wx.TextCtrl(self.new_panel, wx.ID_ANY, default_name)
            sz = wx.BoxSizer(wx.HORIZONTAL)
            sz.Add(wx.StaticText(self.new_panel, wx.ID_ANY, 'Core Name:'),
                        border=5, flag=wx.ALL)
            sz.Add(self.core_name, border=5, proportion=1, flag=wx.ALL | wx.EXPAND)
            self.new_panel.SetSizer(sz)
            
            self.exis_panel = wx.Panel(self, size=(300, -1))
            cores = datastore.cores.keys()
            if not cores:
                self.existing_core.Disable()
            else:
                self.core_select = wx.ComboBox(self.exis_panel, wx.ID_ANY, cores[0],
                                               choices=cores,
                                               style=wx.CB_READONLY)
                sz = wx.BoxSizer(wx.HORIZONTAL)
                sz.Add(wx.StaticText(self.exis_panel, wx.ID_ANY, 'Select Core:'),
                        border=5, flag=wx.ALL)
                sz.Add(self.core_select, border=5, proportion=1, 
                       flag=wx.ALL | wx.EXPAND)
                self.exis_panel.SetSizer(sz)
            
            rsizer = wx.BoxSizer(wx.HORIZONTAL)
            rsizer.Add(self.new_core, border=5, flag=wx.ALL)
            rsizer.Add(self.existing_core, border=5, flag=wx.ALL)
            
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(rsizer, flag=wx.EXPAND)
            sizer.Add(self.new_panel, border=5, flag=wx.ALL)
            sizer.Add(self.exis_panel, border=5, flag=wx.ALL)
            self.SetSizer(sizer)
            
            self.Bind(wx.EVT_RADIOBUTTON, self.on_coretype, self.new_core)
            self.Bind(wx.EVT_RADIOBUTTON, self.on_coretype, self.existing_core)
            self.exis_panel.Hide()
            self.new_core.SetValue(True)
            
        def on_coretype(self, event):
            self.new_panel.Show(self.new_core.GetValue())
            self.exis_panel.Show(self.existing_core.GetValue())
            self.Layout()
            
        #TODO: add validation!
        @property
        def name(self):
            if self.existing_core.GetValue():
                return self.core_select.GetValue()
            else:
                return self.core_name.GetValue()
    
    def __init__(self, parent, csv_file, fields, rows):
        super(DisplayImportedSamples, self).__init__(parent, wx.ID_ANY, 'Import Samples')
        
        #remove file extension
        name = csv_file.rsplit('.', 1)[0]
        grid = self.create_grid(fields, rows)
        
        self.core_panel = DisplayImportedSamples.CorePanel(self, name)
        #panel for adding a source, if one doesn't already exist
        source_panel = wx.Panel(self, style=wx.TAB_TRAVERSAL | wx.BORDER_SIMPLE)
        self.add_source_check = wx.CheckBox(source_panel, wx.ID_ANY, 
                                    "Add 'source' attribute with value: ")
        self.source_name_input = wx.TextCtrl(source_panel, wx.ID_ANY, size=(250, -1),
                                    value=name)
        self.source_name_input.Enable(self.add_source_check.IsChecked())
        source_sizer = wx.BoxSizer(wx.HORIZONTAL)
        source_sizer.Add(self.add_source_check, border=5, flag=wx.ALL)
        source_sizer.Add(self.source_name_input, border=5, flag=wx.ALL)
        source_panel.SetSizer(source_sizer)

        btnsizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self, wx.ID_ANY, 
                    "The following samples are contained in %s:" % csv_file),
                  border=5, flag=wx.ALL)
        sizer.Add(grid, border=5, proportion=1, flag=wx.ALL | wx.EXPAND)
        sizer.Add(self.core_panel, border=5, flag=wx.ALL)
        sizer.Add(source_panel, border=5, flag=wx.ALL)
        sizer.Add(wx.StaticText(self, wx.ID_ANY, 
                    "Do you want to import these samples as displayed?"), 
                  border=5, flag=wx.ALL | wx.ALIGN_CENTER)
        sizer.Add(btnsizer, border=5, flag=wx.ALL | wx.ALIGN_CENTER)

        source_panel.Show('source' not in fields)

        self.SetSizer(sizer)
        sizer.Fit(self)
        
        self.Center(wx.BOTH)

    def create_grid(self, fields, rows):
        g = grid.LabelSizedGrid(self, wx.ID_ANY)
        g.CreateGrid(len(rows), len(fields))
        g.EnableEditing(False)
        for index, att in enumerate(fields):
            g.SetColLabelValue(index, att.replace(' ', '\n'))            
        
        # fill out grid with values
        for row_index, sample in enumerate(rows):
            g.SetRowLabelValue(row_index, str(sample['depth']))
            for col_index, att in enumerate(fields):
                g.SetCellValue(row_index, col_index, str(sample[att]))                
               
        g.AutoSize()
        return g
        
    @property
    def core_name(self):
        return self.core_panel.name
    @property
    def source_name(self):
        return (self.add_source_check.IsChecked() and 
                self.source_name_input.GetValue())
    
    
class ComputationDialog(wx.Dialog):

    def __init__(self, parent, core):
        super(ComputationDialog, self).__init__(parent, id=wx.ID_ANY, 
                                    title="Run Computations")

        self.core = core
        #TODO: exclude plans already run on this core...
        self.planchoice = wx.Choice(self, wx.ID_ANY, 
                choices=["<SELECT PLAN>"] + 
                         sorted(datastore.computation_plans.keys()))
        #TODO: sorting is a bit ew atm, see what I can do?
        self.alldepths = [str(d) for d in sorted(self.core.keys())]
        #TODO: do we want to allow exclusion on computation plans, or not really?
        #self.depthpicker = wx.lib.itemspicker.ItemsPicker(self, wx.ID_ANY,
        #        choices=self.alldepths, 
        #        label='At Depths:', selectedLabel='Exclude Depths:',
        #        ipStyle=wx.lib.itemspicker.IP_REMOVE_FROM_CHOICES)
        #self.depthpicker.add_button_label = "- Exclude ->"
        #self.depthpicker.remove_button_label = "<- Include -"
        
        bsz = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        
        sizer = wx.GridBagSizer(10, 10)
        sizer.Add(wx.StaticText(self, wx.ID_ANY, "Apply Plan"), (0, 0))
        sizer.Add(self.planchoice, (0, 1), flag=wx.EXPAND)
        sizer.Add(wx.StaticText(self, wx.ID_ANY, 'To Core "%s"' % self.core.name), 
                  (1, 0), (1, 2))
        #sizer.Add(self.depthpicker, (2, 0), (1, 2), flag=wx.EXPAND)
        sizer.Add(bsz, (3, 1), flag=wx.ALIGN_RIGHT)
        sizer.AddGrowableRow(2)
        sizer.AddGrowableCol(1)
        self.SetSizer(sizer)
        self.Center()
        
        self.okbtn = self.FindWindowById(self.AffirmativeId)
        self.okbtn.Disable()
        self.Bind(wx.EVT_CHOICE, self.plan_selected, self.planchoice)

    def plan_selected(self, event):
        self.okbtn.Enable(bool(self.planchoice.GetSelection()))
        
    @property
    def plan(self):
        return self.planchoice.GetStringSelection()
    
    @property
    def depths(self):
        #TODO: fix this if some samples can be excluded...
        return self.alldepths
                
class WorkflowProgress(wx.Dialog):
    def __init__(self, parent, title):
        super(WorkflowProgress, self).__init__(parent, wx.ID_ANY, title)
        
        #TODO: make this a real progress bar...
        self.bar = wx.Gauge(self, wx.ID_ANY)
        button = wx.Button(self, wx.ID_CANCEL, 'Abort')
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.bar, border=5, flag=wx.ALL | wx.EXPAND)
        sizer.Add(button, border=5, flag=wx.ALIGN_CENTER | wx.ALL)
        
        self.SetSizer(sizer)

        self.Bind(events.EVT_WORKFLOW_DONE, self.on_finish)
        self.Bind(wx.EVT_TIMER, lambda evt: self.bar.Pulse())
        self.timer = wx.Timer(self)
        self.timer.Start(100)

    def Destroy(self):
        self.timer.Stop()
        return super(WorkflowProgress, self).Destroy()

    def on_finish(self, event):
        self.EndModal(wx.ID_OK)


class AboutBox(wx.Dialog):
    
    about_text = '''<html>
    <body bgcolor="white">
        <center>
            <h1>ACE: Age Calculation Environment</h1>
            <h2>Version 1.0</h2>
            <h3>http://ace.hwr.arizona.edu</h3>
            <table>
                <tr>
                    <th align="center" colspan="2">Contributors</th>
                </tr>
                <tr>
                    <td>Kenneth M. Anderson</td>
                    <td>Laura Rassbach</td>
                </tr>
                <tr>
                    <td>Elizabeth Bradley</td>
                    <td>Evan Sheehan</td>
                </tr>
                <tr>
                    <td>William Van Lepthien</td>
                    <td>Marek Zreda</td>
                </tr>
                <tr>
                    <td align="center" colspan="2">Chris Zweck</td>
                </td>
            </table>
            <p>This software is based upon work sponsored by the NSF under 
               Grant Number ATM-0325812 and Grant Number ATM-0325929.</p>
            <p>Copyright &copy; 2007-2009 University of Colorado. 
               All rights reserved.</p>
        </center>
    </body>
</html>'''
    
    def __init__(self, parent):
        super(AboutBox, self).__init__(parent, wx.ID_ANY, 'About ACE')

        html = wx.html.HtmlWindow(self)
        html.SetPage(AboutBox.about_text)
        link = wx.lib.hyperlink.HyperLinkCtrl(self, wx.ID_ANY, "ACE Website", 
                                              URL="http://ace.hwr.arizona.edu")
        button = wx.Button(self, wx.ID_OK)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(html, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(link, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        sizer.Add(button, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        self.SetSizer(sizer)
        self.Layout()



