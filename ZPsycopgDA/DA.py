# ZPsycopgDA/DA.py - ZPsycopgDA Zope product: Database Connection
#
# Copyright (C) 2004 Federico Di Gregorio <fog@initd.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2, or (at your option) any later
# version.
#
# Or, at your option this program (ZPsycopgDA) can be distributed under the
# Zope Public License (ZPL) Version 1.0, as published on the Zope web site,
# http://www.zope.org/Resources/ZPL.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTIBILITY
# or FITNESS FOR A PARTICULAR PURPOSE.
#
# See the LICENSE file for details.


ALLOWED_PSYCOPG_VERSIONS = ('2.0b4', '2.0b5')

import sys
import time
import db

import Acquisition
import Shared.DC.ZRDB.Connection

from db import DB
from Globals import HTMLFile
from ImageFile import ImageFile
from ExtensionClass import Base
from App.Dialogs import MessageDialog
from DateTime import DateTime

# import psycopg and functions/singletons needed for date/time conversions

import psycopg2
from psycopg2 import NUMBER, STRING, ROWID, DATETIME
from psycopg2.extensions import INTEGER, LONGINTEGER, FLOAT, BOOLEAN, DATE
from psycopg2.extensions import TIME, INTERVAL
from psycopg2.extensions import new_type, register_type



# add a new connection to a folder

manage_addZPsycopgConnectionForm = HTMLFile('dtml/add',globals())

def manage_addZPsycopgConnection(self, id, title, connection_string,
                                 zdatetime=None, tilevel=2,
                                 check=None, REQUEST=None):
    """Add a DB connection to a folder."""
    self._setObject(id, Connection(id, title, connection_string,
                                   zdatetime, check, tilevel))
    if REQUEST is not None: return self.manage_main(self, REQUEST)



# the connection object

class Connection(Shared.DC.ZRDB.Connection.Connection):
    """ZPsycopg Connection."""
    _isAnSQLConnection = 1
    
    id                = 'Psycopg_database_connection' 
    database_type     = 'Psycopg'
    meta_type = title = 'Z Psycopg Database Connection'
    icon              = 'misc_/ZPsycopgDA/conn'

    def __init__(self, id, title, connection_string,
                 zdatetime, check=None, tilevel=2, encoding=''):
        self.zdatetime = zdatetime
        self.id = str(id)
        self.edit(title, connection_string, zdatetime,
                  check=check, tilevel=tilevel, encoding=encoding)
        
    def factory(self):
        return DB

    ## connection parameters editing ##
    
    def edit(self, title, connection_string,
             zdatetime, check=None, tilevel=2, encoding=''):
        self.title = title
        self.connection_string = connection_string
        self.zdatetime = zdatetime
        self.tilevel = tilevel
        self.encoding = encoding

        self.set_type_casts()
        
        if check: self.connect(self.connection_string)

    manage_properties = HTMLFile('dtml/edit', globals())

    def manage_edit(self, title, connection_string,
                    zdatetime=None, check=None, tilevel=2, encoding='UTF-8',
                    REQUEST=None):
        """Edit the DB connection."""
        self.edit(title, connection_string, zdatetime,
                  check=check, tilevel=tilevel, encoding=encoding)
        if REQUEST is not None:
            msg = "Connection edited."
            return self.manage_main(self,REQUEST,manage_tabs_message=msg)

    def connect(self, s):
        try:
            self._v_database_connection.close()
        except:
            pass

        # check psycopg version and raise exception if does not match
        if psycopg2.__version__[:5] not in ALLOWED_PSYCOPG_VERSIONS:
            raise ImportError("psycopg version mismatch (imported %s)" %
                              psycopg2.__version__)

        self.set_type_casts()
        self._v_connected = ''
        dbf = self.factory()
        
        # TODO: let the psycopg exception propagate, or not?
        self._v_database_connection = dbf(
            self.connection_string, self.tilevel, self.encoding)
        self._v_database_connection.open()
        self._v_connected = DateTime()

        return self

    def set_type_casts(self):
        # note that in both cases order *is* important
        if self.zdatetime:
            # use zope internal datetime routines
            register_type(ZDATETIME)
            register_type(ZDATE)
            register_type(ZTIME)
            register_type(ZINTERVAL)
        else:
            # use the standard
            register_type(DATETIME)
            register_type(DATE)
            register_type(TIME)
            register_type(INTERVAL)

    ## browsing and table/column management ##

    manage_options = Shared.DC.ZRDB.Connection.Connection.manage_options + (
        {'label': 'Browse', 'action':'manage_browse'},)

    manage_tables = HTMLFile('dtml/tables', globals())
    manage_browse = HTMLFile('dtml/browse', globals())

    info = None
    
    def table_info(self):
        return self._v_database_connection.table_info()


    def __getitem__(self, name):
        if name == 'tableNamed':
            if not hasattr(self, '_v_tables'): self.tpValues()
            return self._v_tables.__of__(self)
        raise KeyError, name

    def tpValues(self):
        res = []
        conn = self._v_database_connection
        for d in conn.tables(rdb=0):
            try:
                name = d['TABLE_NAME']
                b = TableBrowser()
                b.__name__ = name
                b._d = d
                b._c = c
                try:
                    b.icon = table_icons[d['TABLE_TYPE']]
                except:
                    pass
                r.append(b)
            except:
                pass
        return res


## database connection registration data ##

classes = (Connection,)

meta_types = ({'name':'Z Psycopg Database Connection',
               'action':'manage_addZPsycopgConnectionForm'},)

folder_methods = {
    'manage_addZPsycopgConnection': manage_addZPsycopgConnection,
    'manage_addZPsycopgConnectionForm': manage_addZPsycopgConnectionForm}

__ac_permissions__ = (
    ('Add Z Psycopg Database Connections',
     ('manage_addZPsycopgConnectionForm', 'manage_addZPsycopgConnection')),)

# add icons

misc_={'conn': ImageFile('Shared/DC/ZRDB/www/DBAdapterFolder_icon.gif')}

for icon in ('table', 'view', 'stable', 'what', 'field', 'text', 'bin',
             'int', 'float', 'date', 'time', 'datetime'):
    misc_[icon] = ImageFile('icons/%s.gif' % icon, globals())


## zope-specific psycopg typecasters ##

# convert an ISO timestamp string from postgres to a Zope DateTime object
def _cast_DateTime(str, curs):
    if str:
        # this will split us into [date, time, GMT/AM/PM(if there)]
        dt = str.split(' ')
        if len(dt) > 1:
            # we now should split out any timezone info
            dt[1] = dt[1].split('-')[0]
            dt[1] = dt[1].split('+')[0]
            return DateTime(' '.join(dt[:2]))
        else:
            return DateTime(dt[0])

# convert an ISO date string from postgres to a Zope DateTime object
def _cast_Date(str, curs):
    if str:
        return DateTime(str)

# Convert a time string from postgres to a Zope DateTime object.
# NOTE: we set the day as today before feeding to DateTime so
# that it has the same DST settings.
def _cast_Time(str, curs):
    if str:
        return DateTime(time.strftime('%Y-%m-%d %H:%M:%S',
                                      time.localtime(time.time())[:3]+
                                      time.strptime(str[:8], "%H:%M:%S")[3:]))

# TODO: DateTime does not support intervals: what's the best we can do?
def _cast_Interval(str, curs):
    return str

ZDATETIME = new_type((1184, 1114), "ZDATETIME", _cast_DateTime)
ZINTERVAL = new_type((1186,), "ZINTERVAL", _cast_Interval)
ZDATE = new_type((1082,), "ZDATE", _cast_Date)
ZTIME = new_type((1083,), "ZTIME", _cast_Time)


## table browsing helpers ##

class TableBrowserCollection(Acquisition.Implicit):
    pass

class Browser(Base):
    def __getattr__(self, name):
        try:
            return self._d[name]
        except KeyError:
            raise AttributeError, name

class values:
    def len(self):
        return 1

    def __getitem__(self, i):
        try:
            return self._d[i]
        except AttributeError:
            pass
        self._d = self._f()
        return self._d[i]

class TableBrowser(Browser, Acquisition.Implicit):
    icon = 'what'
    Description = check = ''
    info = HTMLFile('table_info', globals())
    menu = HTMLFile('table_menu', globals())

    def tpValues(self):
        v = values()
        v._f = self.tpValues_
        return v

    def tpValues_(self):
        r=[]
        tname=self.__name__
        for d in self._c.columns(tname):
            b=ColumnBrowser()
            b._d=d
            try: b.icon=field_icons[d['Type']]
            except: pass
            b.TABLE_NAME=tname
            r.append(b)
        return r
            
    def tpId(self): return self._d['TABLE_NAME']
    def tpURL(self): return "Table/%s" % self._d['TABLE_NAME']
    def Name(self): return self._d['TABLE_NAME']
    def Type(self): return self._d['TABLE_TYPE']

    manage_designInput=HTMLFile('designInput',globals())
    def manage_buildInput(self, id, source, default, REQUEST=None):
        "Create a database method for an input form"
        args=[]
        values=[]
        names=[]
        columns=self._columns
        for i in range(len(source)):
            s=source[i]
            if s=='Null': continue
            c=columns[i]
            d=default[i]
            t=c['Type']
            n=c['Name']
            names.append(n)
            if s=='Argument':
                values.append("<dtml-sqlvar %s type=%s>'" %
                              (n, vartype(t)))
                a='%s%s' % (n, boboType(t))
                if d: a="%s=%s" % (a,d)
                args.append(a)
            elif s=='Property':
                values.append("<dtml-sqlvar %s type=%s>'" %
                              (n, vartype(t)))
            else:
                if isStringType(t):
                    if find(d,"\'") >= 0: d=join(split(d,"\'"),"''")
                    values.append("'%s'" % d)
                elif d:
                    values.append(str(d))
                else:
                    raise ValueError, (
                        'no default was given for <em>%s</em>' % n)

class ColumnBrowser(Browser):
    icon='field'

    def check(self):
        return ('\t<input type=checkbox name="%s.%s">' %
                (self.TABLE_NAME, self._d['Name']))
    def tpId(self): return self._d['Name']
    def tpURL(self): return "Column/%s" % self._d['Name']
    def Description(self):
        d=self._d
        if d['Scale']:
            return " %(Type)s(%(Precision)s,%(Scale)s) %(Nullable)s" % d
        else:
            return " %(Type)s(%(Precision)s) %(Nullable)s" % d

table_icons={
    'TABLE': 'table',
    'VIEW':'view',
    'SYSTEM_TABLE': 'stable',
    }

field_icons={
    NUMBER.name: 'i',
    STRING.name: 'text',
    DATETIME.name: 'date',
    INTEGER.name: 'int',
    FLOAT.name: 'float',
    BOOLEAN.name: 'bin',
    ROWID.name: 'int'
    }
