#!/usr/bin/python

# -*- coding: utf-8 -*-

# Copyright (C) 2009-2012:
#    Gabes Jean, naparuba@gmail.com
#    Gerhard Lausser, Gerhard.Lausser@consol.de
#    Gregory Starck, g.starck@gmail.com
#    Hartmut Goebel, h.goebel@goebel-consult.de
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
            self.tag = getattr(mod_conf, 'tag', '')
            self.tags = getattr(mod_conf, 'tags', '')
        except AttributeError:
            logger.error("[GLPI Arbiter] The module is missing a property, check module configuration in import-glpi.cfg")
            raise

    # Called by Arbiter to say 'let's prepare yourself guy'
    def init(self):
        logger.info("[GLPI Arbiter] Connecting to %s" % self.uri)
        self.con = xmlrpclib.ServerProxy(self.uri)
        logger.info("[GLPI Arbiter] Connection opened")
        logger.info("[GLPI Arbiter] Authentication in progress...")
        arg = {'login_name': self.login_name, 'login_password': self.login_password}
        res = self.con.glpi.doLogin(arg)
        self.session = res['session']
        logger.info("[GLPI Arbiter] Authenticated, session : %s" % str(self.session))

    # Ok, main function that will load config from GLPI
    def get_objects(self):
        r = {'commands': [],
             'timeperiods': [],
             'hosts': [],
             'hostgroups': [],
             'services': [],
             'contacts': []}
        logger.debug("[GLPI Arbiter] Tags: %s" % self.tags)
        if len(self.tags) == 0:
            self.tags = self.tag
            
        self.tags = self.tags.split(',')
        logger.debug("[GLPI Arbiter] Tags2: %s" % str(self.tags))
            
        for tag in self.tags:
            tag = tag.strip()
            logger.warning("[GLPI Arbiter] Getting configuration for entity tagged with '%s'" % tag)
            
            arg = {'session': self.session,
                   'tag': tag}

            # Get commands
            all_commands = self.con.monitoring.shinkenCommands(arg)
            logger.info("[GLPI Arbiter] Got commands")
            for command_info in all_commands:
                logger.debug("[GLPI Arbiter] Command info in GLPI: %s" % str(command_info))
                h = {'command_name': command_info['command_name'],
                     'command_line': command_info['command_line'],
                     }
                if 'module_type' in command_info:
                    h.update({'module_type': command_info['module_type']})
                if 'poller_tag' in command_info:
                    h.update({'poller_tag': command_info['poller_tag']})
                if 'reactionner_tag' in command_info:
                    h.update({'reactionner_tag': command_info['reactionner_tag']})
                
                if h not in r['commands']:
                    logger.info("[GLPI Arbiter] New command: %s" % h['command_name'])
                    r['commands'].append(h)

            # Get timeperiods
            all_timeperiods = self.con.monitoring.shinkenTimeperiods(arg)
            logger.info("[GLPI Arbiter] Got timeperiods")
            attributs = ['timeperiod_name', 'alias', 'sunday',
                         'monday', 'tuesday', 'wednesday',
                         'thursday', 'friday', 'saturday']
            for timeperiod_info in all_timeperiods:
                logger.debug("[GLPI Arbiter] Timeperiod info in GLPI: %s" % str(timeperiod_info))
                h = {}
                for attribut in attributs:
                    if attribut in timeperiod_info:
                        h[attribut] = timeperiod_info[attribut]

                if h not in r['timeperiods']:
                    logger.info("[GLPI Arbiter] New timeperiod: %s" % h['timeperiod_name'])
                    r['timeperiods'].append(h)

            # Get hosts
            all_hosts = self.con.monitoring.shinkenHosts(arg)
            logger.info("[GLPI Arbiter] Got hosts")
            attributs = ['use', 'display_name', 'hostgroups', 'initial_state', 
                         'active_checks_enabled', 'passive_checks_enabled', 'obsess_over_host',
                         'check_freshness', 'freshness_threshold', 'event_handler',
                         'event_handler_enabled', 'low_flap_threshold ', 'high_flap_threshold',
                         'flap_detection_enabled', 'flap_detection_options', 'retain_status_information',
                         'retain_nonstatus_information', 'contact_groups', 'first_notification_delay',
                         'notifications_enabled', 'stalking_options', 'notes',
                         'notes_url', 'action_url', 'icon_image', 'icon_set', 'custom_views', 
                         'icon_image_alt', 'vrml_image', 'statusmap_image',
                         '2d_coords', '3d_coords', 'realm',
                         'poller_tag', 'business_impact', '_ENTITIESID', '_ENTITY', '_ITEMSID', '_ITEMTYPE', '_HOSTID', 
                         '_LOC_LAT', '_LOC_LNG']
            for host_info in all_hosts:
                logger.debug("[GLPI Arbiter] Host info in GLPI: %s " % str(host_info))
                h = {'host_name': host_info['host_name'],
                     'alias': host_info['alias'],
                     'address': host_info['address'],
                     'parents': host_info['parents'],
                     'check_command': host_info['check_command'],
                     'check_interval': host_info['check_interval'],
                     'retry_interval': host_info['retry_interval'],
                     'max_check_attempts': host_info['max_check_attempts'],
                     'check_period': host_info['check_period'],
                     'contacts': host_info['contacts'],
                     'process_perf_data': host_info['process_perf_data'],
                     'notification_interval': host_info['notification_interval'],
                     'notification_period': host_info['notification_period'],
                     'notification_options': host_info['notification_options']}
                for attribut in attributs:
                    if attribut in host_info:
                        h[attribut] = host_info[attribut]
                        
                if h not in r['hosts']:
                    logger.info("[GLPI Arbiter] New host: %s" % h['host_name'])
                    r['hosts'].append(h)

            # Get hostgroups
            all_hostgroups = self.con.monitoring.shinkenHostgroups(arg)
            logger.info("[GLPI Arbiter] Got hostgroups")
            attributs = []
            for hostgroup_info in all_hostgroups:
                logger.debug("[GLPI Arbiter] Hostgroup info in GLPI: %s " % str(hostgroup_info))
                h = {'hostgroup_name': hostgroup_info['hostgroup_name'],
                     'alias': hostgroup_info['alias']}
                for attribut in attributs:
                    if attribut in hostgroup_info:
                        h[attribut] = hostgroup_info[attribut]
                        
                if h not in r['hostgroups']:
                    logger.info("[GLPI Arbiter] New hostgroup: %s" % h['hostgroup_name'])
                    r['hostgroups'].append(h)

            # Get templates
            all_templates = self.con.monitoring.shinkenTemplates(arg)
            logger.info("[GLPI Arbiter] Got templates")
            attributs = ['name', 'check_interval', 'retry_interval',
                         'max_check_attempts', 'check_period', 'notification_interval',
                         'notification_period', 'notification_options', 'active_checks_enabled',
                         'process_perf_data', 'active_checks_enabled', 'passive_checks_enabled',
                         'parallelize_check', 'obsess_over_service', 'check_freshness',
                         'freshness_threshold', 'notifications_enabled', 'event_handler_enabled',
                         'event_handler', 'flap_detection_enabled', 'failure_prediction_enabled',
                         'retain_status_information', 'retain_nonstatus_information', 'is_volatile',
                         '_httpstink']
            for template_info in all_templates:
                logger.debug("[GLPI Arbiter] Template info in GLPI: %s" % template_info)
                h = {'register': '0'}
                for attribut in attributs:
                    if attribut in template_info:
                        h[attribut] = template_info[attribut]

                if h not in r['services']:
                    logger.info("[GLPI Arbiter] New service template: %s" % h['name'])
                    r['services'].append(h)

            # Get services
            all_services = self.con.monitoring.shinkenServices(arg)
            logger.info("[GLPI Arbiter] Got services")
            attributs = ['host_name', 'hostgroup_name', 'service_description',
                         'use', 'check_command', 'check_interval', 'retry_interval',
                         'max_check_attempts', 'check_period', 'contacts',
                         'notification_interval', 'notification_period', 'notification_options',
                         'active_checks_enabled', 'process_perf_data',
                         'passive_checks_enabled', 'parallelize_check', 'obsess_over_service',
                         'check_freshness', 'freshness_threshold', 'notifications_enabled',
                         'event_handler_enabled', 'event_handler', 'flap_detection_enabled',
                         'failure_prediction_enabled', 'retain_status_information', 'retain_nonstatus_information',
                         'is_volatile', '_httpstink',
                         'display_name', 'servicegroups', 'initial_state',
                         'low_flap_threshold', 'high_flap_threshold', 'flap_detection_options',
                         'first_notification_delay', 'notifications_enabled', 'contact_groups',
                         'stalking_options', 'notes', 'notes_url',
                         'action_url', 'icon_image', 'icon_image_alt', 'icon_set', 
                         'poller_tag', 'service_dependencies', 'business_impact',
                         '_ENTITIESID', '_ENTITY', '_ITEMSID', '_ITEMTYPE', '_HOSTITEMSID', '_HOSTITEMTYPE']

            for service_info in all_services:
                logger.debug("[GLPI Arbiter] Service info in GLPI: %s" % service_info)
                h = {}
                for attribut in attributs:
                    if attribut in service_info:
                        h[attribut] = service_info[attribut]

                if h not in r['services']:
                    logger.info("[GLPI Arbiter] New service: %s/%s" % (h['host_name'], h['service_description']))
                    r['services'].append(h)

            # Get contacts
            all_contacts = self.con.monitoring.shinkenContacts(arg)
            logger.info("[GLPI Arbiter] Got contacts")
            for contact_info in all_contacts:
                logger.debug("[GLPI Arbiter] Contact info in GLPI: %s" % contact_info)
                c = {'contact_name': contact_info['contact_name'],
                     'alias': contact_info['alias'],
                     'host_notifications_enabled': contact_info['host_notifications_enabled'],
                     'service_notifications_enabled': contact_info['service_notifications_enabled'],
                     'service_notification_period': contact_info['service_notification_period'],
                     'host_notification_period': contact_info['host_notification_period'],
                     'service_notification_options': contact_info['service_notification_options'],
                     'host_notification_options': contact_info['host_notification_options'],
                     'service_notification_commands': contact_info['service_notification_commands'],
                     'host_notification_commands': contact_info['host_notification_commands'],
                     'email': contact_info['email'], 
                     'pager': contact_info['pager'],
                     }
                if 'is_admin' in contact_info:
                    c.update({'is_admin': contact_info['is_admin']})
                    c.update({'password': contact_info['password']})
                if 'address1' in contact_info:
                    c.update({'address1': contact_info['address1']})
                    c.update({'address2': contact_info['address2']})
                    c.update({'address3': contact_info['address3']})
                    c.update({'address4': contact_info['address4']})
                    c.update({'address5': contact_info['address5']})
                    c.update({'address6': contact_info['address6']})
                    
                if c not in r['contacts']:
                    logger.info("[GLPI Arbiter] New contact: %s" % c['contact_name'])
                    r['contacts'].append(c)

        # logger.debug("[GLPI Arbiter] Returning to Arbiter the data: %s" % str(r))
        logger.info("[GLPI Arbiter] Sending all data to Arbiter")
        return r
