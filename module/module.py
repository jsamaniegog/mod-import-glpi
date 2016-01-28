#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2009-2012:
#    Gabes Jean, naparuba@gmail.com
#    Gerhard Lausser, Gerhard.Lausser@consol.de
#    Gregory Starck, g.starck@gmail.com
#    Hartmut Goebel, h.goebel@goebel-consult.de
#    David Durieux, d.durieux@siprossii
#    Frederic Mohier, frederic.mohier@gmail.com
#
# This file is part of Shinken.
#
# Shinken is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Shinken is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Shinken.  If not, see <http://www.gnu.org/licenses/>.


# This Class is a plugin for the Shinken Arbiter. It connect to
# a GLPI with webservice (xmlrpc, SOAP is garbage) and take all
# hosts. Simple way from now

import xmlrpclib
import os

from shinken.basemodule import BaseModule
from shinken.log import logger

properties = {
    'daemons': ['arbiter'],
    'type': 'import-glpi',
    'external': False,
    'phases': ['configuration'],
    }


# called by the plugin manager to get a broker
def get_instance(plugin):
    logger.info("[import-glpi] Get a Simple import-glpi for plugin %s" % plugin.get_name())
    instance = Glpi_arbiter(plugin)
    return instance


# Just get hostname from a GLPI webservices
class Glpi_arbiter(BaseModule):
    def __init__(self, mod_conf):
        BaseModule.__init__(self, mod_conf)
        try:
            self.uri = getattr(mod_conf, 'uri', 'http://localhost/glpi/plugins/webservices/xmlrpc.php')
            self.login_name = getattr(mod_conf, 'login_name', 'shinken')
            self.login_password = getattr(mod_conf, 'login_password', 'shinken')
            # tag is still managed for compatibility purposes, better use tags!
            self.tag = getattr(mod_conf, 'tag', '')
            self.tags = getattr(mod_conf, 'tags', '')
            self.session = None

            # Target to build files on disk
            self.target = getattr(mod_conf, 'target', 'files')
            if self.target == 'files':
                self.target_directory = getattr(mod_conf, 'target_directory', '/etc/shinken/glpi')
                if not os.path.exists(self.target_directory):
                    try:
                        os.mkdir(self.target_directory)
                        logger.info("[import-glpi] Created directory: %s", self.target_directory)
                    except Exception, exp:
                        logger.error("[import-glpi] Directory creation failed: %s", exp)

        except AttributeError:
            logger.error("[import-glpi] The module is missing a property, check module configuration in import-glpi.cfg")
            raise

    # Called by Arbiter to say 'let's prepare yourself guy'
    def init(self):
        """
        Connect to the Glpi Web Service.
        """
        try:
            logger.info("[import-glpi] Connecting to %s" % self.uri)
            self.con = xmlrpclib.ServerProxy(self.uri)
            logger.info("[import-glpi] Connection opened")
            logger.info("[import-glpi] Authentication in progress...")
            arg = {'login_name': self.login_name, 'login_password': self.login_password}
            res = self.con.glpi.doLogin(arg)
            self.session = res['session']
            logger.info("[import-glpi] Authenticated, session : %s" % str(self.session))
        except Exception as e:
            logger.error("[import-glpi] WS connection error: %s", str(e))
            self.con = None

        return self.con

    # Ok, main function that will load config from GLPI
    def get_objects(self):
        r = {'commands': [],
             'timeperiods': [],
             'hosts': [],
             'hostgroups': [],
             'servicestemplates': [],
             'services': [],
             'contacts': []}

        if self.target == 'files':
            return r

        if not self.session:
            logger.error("[import-glpi] No opened session, no objects to provide.")
            return None

        if not self.tags:
            self.tags = self.tag

        logger.debug("[import-glpi] Tags in configuration file: %s" % str(self.tags))
        try:
            self.tags = self.tags.split(',')
        except:
            pass
        logger.info("[import-glpi] Tags (from configuration): %s" % str(self.tags))

        # Try to find sub-tags if they exist in Glpi
        # ---------------------------------------------------------------------------------------
        # WS ShinkenTags:
        # 1/ search for an entity tagged with the provided tag
        # 2/ get the list of this entity's immediate sons
        # 3/ returns the list of the sons' tags
        # ---------------------------------------------------------------------------------------
        # Instead of requesting configuration for an entity, this strategy allows to request
        # configuration from several sub-entities ... to avoid very long request/response time.
        self.new_tags = []
        for tag in self.tags:
            tag = tag.strip()
            logger.info("[import-glpi] Getting Glpi tags for entity tagged with '%s'" % tag)

            # iso8859 is necessary because Arbiter does not deal with UTF8 objects !
            arg = {'session': self.session, 'iso8859': '1', 'tag': tag}

            # Get commands
            all_tags = self.con.monitoring.shinkenTags(arg)
            logger.warning("[import-glpi] Got %d tags", len(all_tags))
            if all_tags:
                # Remove current tag and replace with Glpi provided list ...
                # self.tags.remove(tag)
                for new_tag in all_tags:
                    self.new_tags.append(new_tag)
            else:
                self.new_tags.append(tag)

        logger.info("[import-glpi] Tags (from configuration + Glpi): %s" % str(self.new_tags))

        for tag in self.new_tags:
            tag = tag.strip()
            logger.info("[import-glpi] Getting configuration for entity tagged with '%s'" % tag)

			# iso8859 is necessary because Arbiter does not deal with UTF8 objects !
            arg = {'session': self.session, 'iso8859': '1', 'tag': tag}

            # Get commands
            all_commands = self.con.monitoring.shinkenCommands(arg)
            logger.warning("[import-glpi] Got %d commands", len(all_commands))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            deleted_attributes = []
            for command_info in all_commands:
                logger.debug("[import-glpi] Command info in GLPI: %s" % str(command_info))
                h = command_info
                for attribute in deleted_attributes:
                    if attribute in h:
                        logger.warning("[import-glpi] Delete attribute '%s' for command '%s'", attribute, h['command_name'])
                        del h[attribute]

                if h not in r['commands']:
                    logger.info("[import-glpi] New command: %s" % h['command_name'])
                    r['commands'].append(h)
                    logger.debug("[import-glpi] Command info in Shinken: %s" % str(h))

            # Get hosts
            all_hosts = self.con.monitoring.shinkenHosts(arg)
            logger.warning("[import-glpi] Got %d hosts", len(all_hosts))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            deleted_attributes = []
            for host_info in all_hosts:
                logger.debug("[import-glpi] Host info in GLPI: %s " % str(host_info))
                h = host_info
                for attribute in deleted_attributes:
                    if attribute in h:
                        logger.warning("[import-glpi] Delete attribute '%s' for host '%s'", attribute, h['host_name'])
                        del h[attribute]

                if h not in r['hosts']:
                    logger.info("[import-glpi] New host: %s" % h['host_name'])
                    r['hosts'].append(h)
                    logger.debug("[import-glpi] Host info in Shinken: %s" % str(h))

            # Get hostgroups
            all_hostgroups = self.con.monitoring.shinkenHostgroups(arg)
            logger.info("[import-glpi] Got %d hostgroups", len(all_hostgroups))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            deleted_attributes = []
            for hostgroup_info in all_hostgroups:
                logger.debug("[import-glpi] Hostgroup info in GLPI: %s " % str(hostgroup_info))
                h = hostgroup_info
                for attribute in deleted_attributes:
                    if attribute in h:
                        logger.warning("[import-glpi] Delete attribute '%s' for hostgroup '%s'", attribute, h['hostgroup_name'])
                        del h[attribute]

                if h not in r['hostgroups']:
                    logger.info("[import-glpi] New hostgroup: %s" % h['hostgroup_name'])
                    r['hostgroups'].append(h)
                    logger.debug("[import-glpi] Hostgroup info in Shinken: %s" % str(h))

            # Get templates
            all_templates = self.con.monitoring.shinkenTemplates(arg)
            logger.warning("[import-glpi] Got %d services templates", len(all_templates))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            deleted_attributes = []
            for template_info in all_templates:
                logger.debug("[import-glpi] Template info in GLPI: %s" % template_info)
                h = template_info
                for attribute in deleted_attributes:
                    if attribute in h:
                        logger.warning("[import-glpi] Delete attribute '%s' for service template '%s'", attribute, h['name'])
                        del h[attribute]

                if h not in r['servicestemplates']:
                    logger.info("[import-glpi] New service template: %s" % h['name'])
                    r['servicestemplates'].append(h)
                    logger.debug("[import-glpi] Service template info in Shinken: %s" % str(h))

            # Get services
            all_services = self.con.monitoring.shinkenServices(arg)
            logger.warning("[import-glpi] Got %d services", len(all_services))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            deleted_attributes = []
            for service_info in all_services:
                logger.debug("[import-glpi] Service info in GLPI: %s" % service_info)
                h = service_info
                for attribute in deleted_attributes:
                    if attribute in h:
                        logger.warning("[import-glpi] Delete attribute '%s' for service '%s/%s'", attribute, h['host_name'], h['service_description'])
                        del h[attribute]

                if h not in r['services']:
                    logger.info("[import-glpi] New service: %s/%s" % (h['host_name'], h['service_description']))
                    r['services'].append(h)
                    logger.debug("[import-glpi] Service info in Shinken: %s" % str(h))

            # Get contacts
            all_contacts = self.con.monitoring.shinkenContacts(arg)
            logger.warning("[import-glpi] Got %d contacts", len(all_contacts))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            deleted_attributes = []
            for contact_info in all_contacts:
                logger.debug("[import-glpi] Contact info in GLPI: %s" % contact_info)
                h = contact_info
                for attribute in deleted_attributes:
                    if attribute in h:
                        logger.warning("[import-glpi] Delete attribute '%s' for contact '%s'", attribute, h['contact_name'])
                        del h[attribute]

                if h not in r['contacts']:
                    logger.info("[import-glpi] New contact: %s" % (h['contact_name']))
                    r['contacts'].append(h)
                    logger.debug("[import-glpi] Contact info in Shinken: %s" % str(h))

            # Get timeperiods
            all_timeperiods = self.con.monitoring.shinkenTimeperiods(arg)
            logger.warning("[import-glpi] Got %d timeperiods", len(all_timeperiods))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            deleted_attributes = []
            for timeperiod_info in all_timeperiods:
                logger.debug("[import-glpi] Timeperiod info in GLPI: %s" % str(timeperiod_info))
                h = timeperiod_info
                for attribute in deleted_attributes:
                    if attribute in h:
                        logger.warning("[import-glpi] Delete attribute '%s' for timeperiod '%s'", attribute, h['timeperiod_name'])
                        del h[attribute]

                if h not in r['timeperiods']:
                    logger.info("[import-glpi] New timeperiod: %s" % h['timeperiod_name'])
                    r['timeperiods'].append(h)
                    logger.debug("[import-glpi] Timeperiod info in Shinken: %s" % str(h))

        logger.warning("[import-glpi] Sending %d commands to Arbiter", len(r['commands']))
        logger.warning("[import-glpi] Sending %d hosts to Arbiter", len(r['hosts']))
        logger.warning("[import-glpi] Sending %d hosts groups to Arbiter", len(r['hostgroups']))
        logger.warning("[import-glpi] Sending %d services templates to Arbiter", len(r['servicestemplates']))
        logger.warning("[import-glpi] Sending %d services to Arbiter", len(r['services']))
        logger.warning("[import-glpi] Sending %d timeperiods to Arbiter", len(r['timeperiods']))
        logger.warning("[import-glpi] Sending %d contacts to Arbiter", len(r['contacts']))
        logger.info("[import-glpi] Sending all data to Arbiter")

        r['services'] = r['services'] + r['servicestemplates']
        del r['servicestemplates']

        return r

    # Load configuration files from Glpi
    def get_files(self):
        result = []

        if not self.session:
            print("[import-glpi] No opened session, no objects to provide.")
            return None

        if not self.tags:
            self.tags = self.tag

        print("[import-glpi] Tags in configuration file: %s" % str(self.tags))
        try:
            self.tags = self.tags.split(',')
        except:
            pass
        print("[import-glpi] Tags (from configuration): %s" % str(self.tags))

        # Try to find sub-tags if they exist in Glpi
        # ---------------------------------------------------------------------------------------
        # WS ShinkenTags:
        # 1/ search for an entity tagged with the provided tag
        # 2/ get the list of this entity's immediate sons
        # 3/ returns the list of the sons' tags
        # ---------------------------------------------------------------------------------------
        # Instead of requesting configuration for an entity, this strategy allows to request
        # configuration from several sub-entities ... to avoid very long request/response time.
        self.new_tags = []
        for tag in self.tags:
            tag = tag.strip()
            print("[import-glpi] Getting Glpi tags for entity tagged with '%s'" % tag)

            # iso8859 is necessary because Arbiter does not deal with UTF8 objects !
            arg = {'session': self.session, 'iso8859': '1', 'tag': tag}

            # Get commands
            all_tags = self.con.monitoring.shinkenTags(arg)
            print("[import-glpi] Got %d tags" % len(all_tags))
            if all_tags:
                # Remove current tag and replace with Glpi provided list ...
                # self.tags.remove(tag)
                for new_tag in all_tags:
                    self.new_tags.append(new_tag)
            else:
                self.new_tags.append(tag)

        print("[import-glpi] Tags (from configuration + Glpi): %s" % str(self.new_tags))

        for tag in self.new_tags:
            tag = tag.strip()
            print("[import-glpi] Getting configuration files for entity tagged with '%s'" % tag)

			# iso8859 is necessary because Arbiter does not deal with UTF8 objects !
            arg = {
                'session': self.session,
                'iso8859': '1',
                'file': 'all',
                'tag': tag
            }

            # Get files
            all_files = self.con.monitoring.shinkenGetConffiles(arg)
            print("[import-glpi] Got %d files" % len(all_files))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            for file in all_files:
                print("[import-glpi] configuration file received from GLPI: %s" % file)
                # logger.info("[import-glpi] file content: %s" % all_files[file])
                filename = os.path.join(self.target_directory, "%s-%s" % (tag, file))

                if filename not in result:
                    print("[import-glpi] creating new file: %s ..." % filename)
                    result.append(filename)

                    try:
                        with os.fdopen(os.open(filename, os.O_WRONLY | os.O_CREAT, 0o644), 'w') as cfg_file:
                            try:
                                cfg_file.write(all_files[file].encode('utf8', 'ignore'))
                                # if isinstance(ticket[field], basestring):
                                    # ticket[field] = ticket[field].encode('utf8', 'ignore')
                                    # logger.info("[glpi-helpdesk] getTicket, field: %s = %s", field, ticket[field])
                            except UnicodeEncodeError:
                                print("[import-glpi] Error when encoding file content: %s - %s" % (filename, str(e)))
                                pass
                        print("[import-glpi] created file: %s" % filename)
                    except Exception as e:
                        print("[import-glpi] Error when writing file: %s - %s" % (filename, str(e)))
                        print("[import-glpi] file content: %s" % all_files[file])

        print("[import-glpi] received %d files from Glpi" % len(result))

        return result

if __name__ == '__main__':
    from shinken.objects.config import Config
    conf = Config()
    buf = conf.read_config(['/etc/shinken/modules/import-glpi.cfg', '/usr/local/etc/shinken/modules/import-glpi.cfg'])
    cfg_objects = conf.read_config_buf(buf)
    conf.create_objects_for_type(cfg_objects, 'module')
    module = None
    for mod in conf.modules:
        if mod.get_name() == 'import-glpi':
            module = mod

    if module:
        instance = Glpi_arbiter(module)
        instance.init()
        if instance.get_files():
            exit(0)

    print("[import-glpi] Error !")
    exit(1)
