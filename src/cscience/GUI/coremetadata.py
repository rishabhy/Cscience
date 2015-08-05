"""
coremetadata.py
* Copyright (c) 2012-2015, University of Colorado.
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
This module lays out the data structure for displaying metadata of cores and virtual cores
"""

import wx
import json
import collections

""" Code adapted from DVC_DataViewModel.py in demo code """

#----------------------------------------------------------------------
# We'll use instaces of these classes to hold our data. Items in the
# tree will get associated back to the coresponding mdCoreAttribute or core object.

class mdCoreAttribute(object):
    # Attributes for a mdCore or mdCompPlan
    def __init__(self, cplan, name, value, jsonKey):
        self.name = name
        self.value = str(value)  # convert the value to string for display
        self.cplan = cplan
        self.jsonKey = jsonKey

    def __repr__(self):
        return 'Attribute: %s-%s' % (self.name, self.value)
    def toJSON(self):
        key = self.jsonKey
        value = self.value
        return key, value

class mdCoreGeoAtt(mdCoreAttribute):
    def __init__(self, cplan, name, value, site, jsonKey='geo'):
        self.lat = value[0]
        self.lon = value[1]
        try:
            self.elev = value[3]
        except:
            self.elev = 'NA'
        self.site = site
        mdCoreAttribute.__init__(self, cplan, name, [self.lat, self.lon, self.elev], jsonKey)

    def __repr__(self):
        return 'Geo: (' + self.lat + ', ' + self.lon + ', ' + self.elev +')'

    def toJSON(self):
        key = self.jsonKey
        value = {"type":"Feature",
                       "geometry":{
                            "type":"Point",
                            "coordinates":[self.lat,self.lon,self.elev]
                       },
                       "properties":{
                            "siteName":self.site
                       }}
        return key, value

class mdCorePubAtt(mdCoreAttribute):
    def __init__(self, cplan, name, value, jsonKey = 'pub'):
        mdCoreAttribute.__init__(cplan, name, value, jsonKey)
    def toJSON(self):
        key = self.jsonKey
        value = self.value
        return key, value

class mdDataTable(object):
    def __init__(self, name, fname, jsonKey):
        self.columns = []
        self.name = name
        self.fname = fname
        self.key = jsonKey
    def __toJSON__(self):
        key = jsonKey
        #TODO: construct the JSON object

class mdPaleoDT(mdDataTable):
    def __init__(self, name, fname):
        mdDataTable.__init__(name, fname, 'paleoData')

class mdChronDT(mdDataTable):
    def __init__(self, name, fname):
        mdDataTable.__init__(name, fname, 'chronData')


class mdTableColumn(object):
    def __init__(self, num, param, pType, units, desc, dType="", notes=""):
        self.number = num #column number
        self.parameter = param # name of the column
        self.parameterType = pType # measured/inferred
        self.units = units # engineering units
        self.description = desc # description
        self.datatype = dType # string, float, int, bool, etc.
        self.notes = notes
    def __repr__(self):
        return 'Column: ' + self.parameter
    def __toJSON__(self):
        return self.__dict__

class mdDict(collections.MutableMapping,dict):
    @property
    def parent(self):
        return self._parent
    @parent.setter
    def parent(self,val):
        if isinstance(val, mdCore):
            self._parent = val
        else:
            exception('Expected val to be of type mdCore')
    def __getitem__(self,key):
        return dict.__getitem__(self,key)
    def __setitem__(self, key, value):
        dict.__setitem__(self,key,value)
        self.parent.update_gui_table()
    def __delitem__(self, key):
        dict.__delitem__(self,key)
    def __iter__(self):
        return dict.__iter__(self)
    def __len__(self):
        return dict.__len__(self)
    def __contains__(self, x):
        return dict.__contains__(self,x)

class mdCore(object):
    def cb_default():
        TypeError('callback has not been set')
    # metadata for original imported core, with no computation plan
    def __init__(self, name, callback=cb_default):
        self._name = name
        self._dispcallback = callback
        self.atts = mdDict({})
        self.atts.parent = self
        self.cps = mdDict({})
        self.cps.parent = self
        self._LiPD = {}

    def update_gui_table(self):
        if self.callback:
            self.callback()
        else:
            TypeError('Expected function as argument')

    # Get and Set the function to update the display of metadata, this runs when
    # a property is updated
    @property
    def callback(self):
        return self._dispcallback

    @callback.setter
    def callback(self, value):
        if callable(value):
            self._dispcallback = value
        else:
            raise ValueError('Expected function as argument')

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self.update_gui_table()

    @property
    def LiPD(self):
        #code to generate LiPD structure
        pass

    def __repr__(self):
        return 'Core: ' + self.name

class mdCompPlan(mdCore):
    # metadata for a virtualcore: has a parent core
    def __init__(self, name):
        mdCore.__init__(self, name)

    def __repr__(self):
        return 'CP: ' + self.name

#----------------------------------------------------------------------
