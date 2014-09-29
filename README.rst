.. image:: https://api.travis-ci.org/shinken-monitoring/mod-import-glpi.svg?branch=master
  :target: https://travis-ci.org/shinken-monitoring/mod-import-glpi
.. _gpli_import_module:

=========================
Shinken GLPI integration 
=========================


Shinken supports importing hosts from GLPI

For people not familiar with GLPI, it is an Open-Source CMDB. Applicable to servers, routers, printers or anything you want for that matter. It is also a help-desk tool. GLPI also integrates with tools like FusionInventory for IT inventory management.

You can still have flat files AND GLPI if you want. Hosts imported from GLPI will be treated as standard hosts from flat file (inheritance, groups, etc). In fact, in this first version the module only sends the host_name to Shinken, but there should be more information extracted like network connexions for parents relations in the future. :)



Requirements 
=============

  - Compatible version of GLPI Shinken module and GLPI version

The current version needs: 
 - plugin monitoring 0.84+1.1 for GLPI.
 - plugin WebServices for GLPI

 See https://forge.indepnet.net to get the plugins.


Enabling GLPI Shinken module 
=============================

To use the import-glpi module you must declare it in your arbiter configuration.

::

  define arbiter {
      ... 

      modules    	 ..., import-glip

  }


The module configuration is defined in the file: import-glpi.cfg.

Default configuration nedds to be tuned up to your Glpi configuration. 

At first, you need to activate and configure the GLPI WebServices to allow 
connection from your Shinken server.
Then you set the WS URI (uri) and the login information (login_name / login_password) 
parameters in the configuration file.

Default is that all hosts known from the plugin Monitoring are monitored by Shinken. 
If you want to monitor only some of them, you may use the tags parameter to set a alit
of Glpi entities to be monitored.
For each entity, you need to configure a tag that you will use in the configuration file.

::

  ## Module:      import-glpi
  ## Loaded by:   Arbiter
  # Loads configuration from GLPI web application.
  # All configuration read from the DB will be added to those read from the
  # standard flat files. -- Be careful of duplicated names!
  # GLPI needs Webservices and Monitoring plugins installed and enabled.
  define module {
      module_name     import-glpi
      module_type     import-glpi
      
      # Glpi Web service URI
      uri             http://localhost/glpi/plugins/webservices/xmlrpc.php
      
      # Default : shinken
      login_name      shinken
      # Default : shinken
      login_password  shinken
     
      # Default : empty to get all objects declared in GLPI
      # Tag may be associated with a Glpi entity to filter monitored hosts/services
      # Note: still usable for compatibility purpose, it is better to use tags attribute
      #tag             Parc_CNAMTS
      # Default : empty to get all objects declared in GLPI
      # tags may contain a list of tags to get several entities from GLPI
      # When getting objects from several entities, the module deletes duplicate objects
      tag             CPAM_Paris
      tags            CPAM_Paris, CPAM_Roubaix, Parc_IPM
  }

It's done :)
