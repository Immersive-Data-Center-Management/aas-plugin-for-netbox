from netbox.plugins import PluginMenuItem


menu_items = (
    PluginMenuItem(
        link='plugins:aas_integration:aasconnection_list',
        link_text='AAS Connections',
    ),
    PluginMenuItem(
        link='plugins:aas_integration:submodeltemplate_list',
        link_text='Submodel Templates',
    ),
    PluginMenuItem(
        link='plugins:aas_integration:submodelconfiguration_list',
        link_text='Submodel Mapping Configurations',
    ),
    PluginMenuItem(
        link='plugins:aas_integration:aas_sync',
        link_text='Sync to AAS',
    ),
)
