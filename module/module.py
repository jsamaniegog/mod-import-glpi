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
    logger.info("[GLPI Arbiter] Get a Simple GLPI arbiter for plugin %s" % plugin.get_name())
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
                        logger.info("[GLPI Arbiter] Created directory: %s", self.target_directory)
                    except Exception, exp:
                        logger.error("[GLPI Arbiter] Directory creation failed: %s", exp)

        except AttributeError:
            logger.error("[GLPI Arbiter] The module is missing a property, check module configuration in import-glpi.cfg")
            raise

    # Called by Arbiter to say 'let's prepare yourself guy'
    def init(self):
        """
        Connect to the Glpi Web Service.
        """
        try:
            logger.info("[GLPI Arbiter] Connecting to %s" % self.uri)
            self.con = xmlrpclib.ServerProxy(self.uri)
            logger.info("[GLPI Arbiter] Connection opened")
            logger.info("[GLPI Arbiter] Authentication in progress...")
            arg = {'login_name': self.login_name, 'login_password': self.login_password}
            res = self.con.glpi.doLogin(arg)
            self.session = res['session']
            logger.info("[GLPI Arbiter] Authenticated, session : %s" % str(self.session))
        except Exception as e:
            logger.error("[GLPI Arbiter] WS connection error: %s", str(e))
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
            self.get_files()
            return r

        if not self.session:
            logger.error("[GLPI Arbiter] No opened session, no objects to provide.")

        if not self.tags:
            self.tags = self.tag

        logger.debug("[GLPI Arbiter] Tags in configuration file: %s" % str(self.tags))
        try:
            self.tags = self.tags.split(',')
        except:
            pass
        logger.info("[GLPI Arbiter] Tags (from configuration): %s" % str(self.tags))

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
            logger.info("[GLPI Arbiter] Getting configuration for entity tagged with '%s'" % tag)

			# iso8859 is necessary because Arbiter does not deal with UTF8 objects !
            arg = {'session': self.session, 'iso8859': '1', 'tag': tag}

            # Get commands
            all_commands = self.con.monitoring.shinkenCommands(arg)
            logger.warning("[GLPI Arbiter] Got %d commands", len(all_commands))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            deleted_attributes = []
            for command_info in all_commands:
                logger.debug("[GLPI Arbiter] Command info in GLPI: %s" % str(command_info))
                h = command_info
                for attribute in deleted_attributes:
                    if attribute in h:
                        logger.warning("[GLPI Arbiter] Delete attribute '%s' for command '%s'", attribute, h['command_name'])
                        del h[attribute]

                if h not in r['commands']:
                    logger.info("[GLPI Arbiter] New command: %s" % h['command_name'])
                    r['commands'].append(h)
                    logger.debug("[GLPI Arbiter] Command info in Shinken: %s" % str(h))

            # Get hosts
            all_hosts = self.con.monitoring.shinkenHosts(arg)
            logger.warning("[GLPI Arbiter] Got %d hosts", len(all_hosts))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            deleted_attributes = []
            for host_info in all_hosts:
                logger.debug("[GLPI Arbiter] Host info in GLPI: %s " % str(host_info))
                h = host_info
                for attribute in deleted_attributes:
                    if attribute in h:
                        logger.warning("[GLPI Arbiter] Delete attribute '%s' for host '%s'", attribute, h['host_name'])
                        del h[attribute]

                if h not in r['hosts']:
                    logger.info("[GLPI Arbiter] New host: %s" % h['host_name'])
                    r['hosts'].append(h)
                    logger.debug("[GLPI Arbiter] Host info in Shinken: %s" % str(h))

            # Get hostgroups
            all_hostgroups = self.con.monitoring.shinkenHostgroups(arg)
            logger.info("[GLPI Arbiter] Got %d hostgroups", len(all_hostgroups))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            deleted_attributes = []
            for hostgroup_info in all_hostgroups:
                logger.debug("[GLPI Arbiter] Hostgroup info in GLPI: %s " % str(hostgroup_info))
                h = hostgroup_info
                for attribute in deleted_attributes:
                    if attribute in h:
                        logger.warning("[GLPI Arbiter] Delete attribute '%s' for hostgroup '%s'", attribute, h['hostgroup_name'])
                        del h[attribute]

                if h not in r['hostgroups']:
                    logger.info("[GLPI Arbiter] New hostgroup: %s" % h['hostgroup_name'])
                    r['hostgroups'].append(h)
                    logger.debug("[GLPI Arbiter] Hostgroup info in Shinken: %s" % str(h))

            # Get templates
            all_templates = self.con.monitoring.shinkenTemplates(arg)
            logger.warning("[GLPI Arbiter] Got %d services templates", len(all_templates))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            deleted_attributes = []
            for template_info in all_templates:
                logger.debug("[GLPI Arbiter] Template info in GLPI: %s" % template_info)
                h = template_info
                for attribute in deleted_attributes:
                    if attribute in h:
                        logger.warning("[GLPI Arbiter] Delete attribute '%s' for service template '%s'", attribute, h['name'])
                        del h[attribute]

                if h not in r['servicestemplates']:
                    logger.info("[GLPI Arbiter] New service template: %s" % h['name'])
                    r['servicestemplates'].append(h)
                    logger.debug("[GLPI Arbiter] Service template info in Shinken: %s" % str(h))

            # Get services
            all_services = self.con.monitoring.shinkenServices(arg)
            logger.warning("[GLPI Arbiter] Got %d services", len(all_services))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            deleted_attributes = []
            for service_info in all_services:
                logger.debug("[GLPI Arbiter] Service info in GLPI: %s" % service_info)
                h = service_info
                for attribute in deleted_attributes:
                    if attribute in h:
                        logger.warning("[GLPI Arbiter] Delete attribute '%s' for service '%s/%s'", attribute, h['host_name'], h['service_description'])
                        del h[attribute]

                if h not in r['services']:
                    logger.info("[GLPI Arbiter] New service: %s/%s" % (h['host_name'], h['service_description']))
                    r['services'].append(h)
                    logger.debug("[GLPI Arbiter] Service info in Shinken: %s" % str(h))

            # Get contacts
            all_contacts = self.con.monitoring.shinkenContacts(arg)
            logger.warning("[GLPI Arbiter] Got %d contacts", len(all_contacts))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            deleted_attributes = []
            for contact_info in all_contacts:
                logger.debug("[GLPI Arbiter] Contact info in GLPI: %s" % contact_info)
                h = contact_info
                for attribute in deleted_attributes:
                    if attribute in h:
                        logger.warning("[GLPI Arbiter] Delete attribute '%s' for contact '%s'", attribute, h['contact_name'])
                        del h[attribute]

                if h not in r['contacts']:
                    logger.info("[GLPI Arbiter] New contact: %s" % (h['contact_name']))
                    r['contacts'].append(h)
                    logger.debug("[GLPI Arbiter] Contact info in Shinken: %s" % str(h))

            # Get timeperiods
            all_timeperiods = self.con.monitoring.shinkenTimeperiods(arg)
            logger.warning("[GLPI Arbiter] Got %d timeperiods", len(all_timeperiods))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            deleted_attributes = []
            for timeperiod_info in all_timeperiods:
                logger.debug("[GLPI Arbiter] Timeperiod info in GLPI: %s" % str(timeperiod_info))
                h = timeperiod_info
                for attribute in deleted_attributes:
                    if attribute in h:
                        logger.warning("[GLPI Arbiter] Delete attribute '%s' for timeperiod '%s'", attribute, h['timeperiod_name'])
                        del h[attribute]

                if h not in r['timeperiods']:
                    logger.info("[GLPI Arbiter] New timeperiod: %s" % h['timeperiod_name'])
                    r['timeperiods'].append(h)
                    logger.debug("[GLPI Arbiter] Timeperiod info in Shinken: %s" % str(h))

        logger.warning("[GLPI Arbiter] Sending %d commands to Arbiter", len(r['commands']))
        logger.warning("[GLPI Arbiter] Sending %d hosts to Arbiter", len(r['hosts']))
        logger.warning("[GLPI Arbiter] Sending %d hosts groups to Arbiter", len(r['hostgroups']))
        logger.warning("[GLPI Arbiter] Sending %d services templates to Arbiter", len(r['servicestemplates']))
        logger.warning("[GLPI Arbiter] Sending %d services to Arbiter", len(r['services']))
        logger.warning("[GLPI Arbiter] Sending %d timeperiods to Arbiter", len(r['timeperiods']))
        logger.warning("[GLPI Arbiter] Sending %d contacts to Arbiter", len(r['contacts']))
        logger.info("[GLPI Arbiter] Sending all data to Arbiter")

        r['services'] = r['services'] + r['servicestemplates']
        del r['servicestemplates']

        return r

    # Load configuration files from Glpi
    def get_files(self):
        r = {'files': []}

        if not self.session:
            logger.error("[GLPI Arbiter] No opened session, no objects to provide.")

        if not self.tags:
            self.tags = self.tag

        logger.debug("[GLPI Arbiter] Tags in configuration file: %s" % str(self.tags))
        try:
            self.tags = self.tags.split(',')
        except:
            pass
        logger.info("[GLPI Arbiter] Tags (from configuration): %s" % str(self.tags))

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
            logger.info("[GLPI Arbiter] Getting configuration files for entity tagged with '%s'" % tag)

			# iso8859 is necessary because Arbiter does not deal with UTF8 objects !
            arg = {
                'session': self.session,
                'iso8859': '1',
                'file': 'all',
                'tag': tag
            }

            # Get files
            all_files = self.con.monitoring.shinkenGetConffiles(arg)
            logger.warning("[GLPI Arbiter] Got %d files", len(all_files))
            # List attributes provided by Glpi and that need to be deleted for Shinken
            for file in all_files:
                logger.info("[GLPI Arbiter] configuration file received from GLPI: %s" % file)
                # logger.info("[GLPI Arbiter] file content: %s" % all_files[file])
                filename = os.path.join(self.target_directory, "%s-%s" % (tag, file))

                if filename not in r['files']:
                    logger.info("[GLPI Arbiter] creating new file: %s ..." % filename)
                    r['files'].append(filename)

                    try:
                        with os.fdopen(os.open(filename, os.O_WRONLY | os.O_CREAT, 0o644), 'w') as cfg_file:
                            try:
                                cfg_file.write(all_files[file].encode('utf8', 'ignore'))
                                # if isinstance(ticket[field], basestring):
                                    # ticket[field] = ticket[field].encode('utf8', 'ignore')
                                    # logger.info("[glpi-helpdesk] getTicket, field: %s = %s", field, ticket[field])
                            except UnicodeEncodeError:
                                logger.error("[GLPI Arbiter] Error when encoding file content: %s - %s" % (filename, str(e)))
                                pass
                        logger.info("[GLPI Arbiter] created file: %s" % filename)
                    except Exception as e:
                        logger.error("[GLPI Arbiter] Error when writing file: %s - %s" % (filename, str(e)))
                        logger.error("[GLPI Arbiter] file content: %s" % all_files[file])

        logger.warning("[GLPI Arbiter] received %d files from Glpi" % len(r['files']))

        return r

# if __name__ == '__main__':
    # conf = {
    # }

    # instance = Glpi_arbiter(conf)
