"""
datastore.py

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

This module holds and manages instances of the objects used to access
data storage for CScience.
"""

import os
import sys
import time
from os.path import expanduser
import logging

from cscience import framework
import cscience.components
import subprocess
import atexit



class SingletonType(type):
    def __call__(cls, *args, **kwargs):
        try:
            return cls.__instance
        except AttributeError:
            cls.__instance = super(SingletonType, cls).__call__(*args, **kwargs)
            return cls.__instance


class Datastore(object):
    # Set this class as a singleton, this is an alternate solution to placing the Datastore() object in the sys.modules dictionary
    __metaclass__ = SingletonType

    data_modified = False
    data_source = ''

    models = {'sample_attributes':framework.Attributes,
              'cores':framework.Cores,
              'templates':framework.Templates,
              'milieus':framework.Milieus,
              #'selectors':framework.Selectors,
              'workflows':framework.Workflows,
              'computation_plans':framework.ComputationPlans,
              'filters':framework.Filters,
              'views':framework.Views}

    component_library = cscience.components.library

    def __init__(self):
        #load up the component library, which doesn't depend on the data source.
        self._logger = logging.getLogger(__name__)

        if getattr(sys, 'frozen', False):
            # we are running in a |PyInstaller| bundle
            basedir = sys._MEIPASS
        else:
            # we are running in a normal Python environment
            basedir = os.path.dirname(__file__)

        # Commented out for pyinstaller to work, does not seem to make a difference in the current code.
        #TODO: Check if this block is necessary and if so, update it to use the correct path for the installer version

        path = os.path.split(cscience.components.__file__)[0]

        for filename in os.listdir(path):
            if not filename.endswith('.py'):
                continue
            module = 'components.%s' % filename[:-len('.py')]
            try:
                __import__(module, globals(), locals())
            except:
                print "problem importing module", module
                print sys.exc_info()
                import traceback
                print traceback.format_exc()

    def set_data_source(self, backend, source):
        """
        Set the source for repository data and do any appropriate initialization.
        """

        #this source is a designation for an hbase datastore where all data for
        #the program will be stored (of doom)
        #typically this will be a server address, at this time.
        self.data_source = source
        #all hbase currently on default port. Fix this.
        self.database = backend.Database(source)

        for model_name, model_class in self.models.iteritems():
            setattr(self, model_name, model_class.load(self.database))
        self.data_modified = False

    def save_datastore(self):
        for model_name in self.models:
            getattr(self, model_name).save()
        self.data_modified = False

    class RepositoryException(Exception): pass

    def kill_database(self):
        executable_path = os.path.join(sys._MEIPASS, "database", "cscience_mongo")
        subprocess.call([executable_path, "localhost:27018", "--eval", "db.getSiblingDB('admin').shutdownServer()"])


    def setup_database(self):


        self._logger.debug("Setting up the database...")

        # Check if the database folder has been created
        database_dir = os.path.join(expanduser("~"), 'cscibox', 'data')
        is_windows = sys.platform.startswith('win')
        database_folder_name = "database_win32" if is_windows else 'database'
        new_database = False
        if not (os.path.exists(database_dir) or os.path.isdir(database_dir)):
            self._logger.debug("'data' diretory does not exist, creating...")
            # Need to create the database files
            try:
                os.makedirs(database_dir)
                new_database = True
            except Exception as e:
                raise Exception("Error creating database directory({0}: {1}".format(database_dir, e.message))

        if os.path.isdir(database_dir):

            self._logger.debug("attempting to start mongodb...")

            # Start mongod and restore the database
            if getattr(sys, 'frozen', False):
                # we are running in a |PyInstaller| bundle
                executable_path = os.path.join(sys._MEIPASS, database_folder_name, "cscience_mongod")
                try:
                    kwargs = {}
                    if is_windows:
                        if subprocess.mswindows:
                            su = subprocess.STARTUPINFO()
                            su.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            su.wShowWindow = subprocess.SW_HIDE
                            kwargs['startupinfo'] = su
                    subprocess.Popen([executable_path, "--fork", "--logpath", database_dir+"/mongo.db", "--dbpath", database_dir, "--port", "27018"], **kwargs)
                except Exception as e:
                    raise Exception("Error starting mongodb: {0}".format(e.message))
                atexit.register(self.kill_database)
                self._logger.debug("mongodb started on port 27018...")

        if new_database:
             self._logger.debug("this is a new installation, attempting to restore the database...")
            # Restore the database
            executable_path = os.path.join(sys._MEIPASS, database_folder_name, "cscience_mongorestore")
            data_files_path = os.path.join(sys._MEIPASS, "database", "dump")

            self._logger.debug("executing {} {} {} {}...".format(executable_path, "-h", "localhost:27018", data_files_path))

            subprocess.Popen([executable_path, "-h", "localhost:27018", data_files_path]).wait()

            self._logger.debug("database restored successfully, starting the applicaiton now.")


#sys.modules[__name__] = Datastore()

