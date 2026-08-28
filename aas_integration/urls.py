from django.urls import path
from . import views

urlpatterns = [
    # Connection management
    path('connections/', views.AASConnectionListView.as_view(), name='aasconnection_list'),
    path('connections/create/', views.AASConnectionCreateView.as_view(), name='aasconnection_create'),
    path('connections/<int:pk>/', views.AASConnectionDetailView.as_view(), name='aasconnection_detail'),
    path('connections/<int:pk>/edit/', views.AASConnectionUpdateView.as_view(), name='aasconnection_edit'),
    path('connections/<int:pk>/delete/', views.AASConnectionDeleteView.as_view(), name='aasconnection_delete'),
    path('connections/<int:pk>/test/', views.test_connection, name='test_connection'),

    # Sync operations
    path('sync/', views.AASSyncView.as_view(), name='aas_sync'),
    path('sync/validate/', views.validate_sync_data, name='validate_sync'),
    path('sync/assets/', views.sync_assets_to_aas, name='sync_assets'),

    # SubmodelTemplate management
    path('templates/', views.SubmodelTemplateListView.as_view(), name='submodeltemplate_list'),
    path('templates/<uuid:pk>/', views.SubmodelTemplateDetailView.as_view(), name='submodeltemplate_detail'),
    path('templates/<uuid:pk>/delete/', views.delete_submodel_template, name='submodeltemplate_delete'),

    # SubmodelConfiguration management
    path('configurations/', views.SubmodelConfigurationListView.as_view(), name='submodelconfiguration_list'),
    path('configurations/create/', views.SubmodelConfigurationCreateView.as_view(), name='submodelconfiguration_create'),
    path('configurations/create/<uuid:template_id>/', views.SubmodelConfigurationCreateView.as_view(), name='submodelconfiguration_create_for_template'),
    path('configurations/<uuid:pk>/', views.SubmodelConfigurationDetailView.as_view(), name='submodelconfiguration_detail'),
    path('configurations/<uuid:pk>/edit/', views.SubmodelConfigurationUpdateView.as_view(), name='submodelconfiguration_edit'),
    path('configurations/<uuid:pk>/delete/', views.delete_submodel_configuration, name='submodelconfiguration_delete'),

    # FieldMapping management
    path('configurations/<uuid:config_id>/mappings/create/', views.FieldMappingCreateView.as_view(), name='fieldmapping_create'),
    path('mappings/<uuid:pk>/edit/', views.FieldMappingUpdateView.as_view(), name='fieldmapping_edit'),
    path('mappings/<uuid:pk>/delete/', views.delete_field_mapping, name='fieldmapping_delete'),
]
