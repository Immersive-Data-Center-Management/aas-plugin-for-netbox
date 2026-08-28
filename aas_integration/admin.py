from django.contrib import admin
from django.utils.html import format_html
from .models import (
    AASConnection,
    SubmodelTemplate,
    SubmodelElement,
    SubmodelConfiguration,
    FieldMapping,
    EntityTypeConfiguration
)


# Inline admin classes for nested editing (defined first for reference in main admin classes)
class SubmodelElementInline(admin.TabularInline):
    """Inline editor for SubmodelElements within a SubmodelTemplate"""
    model = SubmodelElement
    extra = 0
    fields = ('id_short', 'element_type', 'value_type', 'semantic_id', 'cardinality', 'order', 'parent_element')
    readonly_fields = ('id',)
    ordering = ('order', 'id_short')
    show_change_link = True


class FieldMappingInline(admin.TabularInline):
    """Inline editor for FieldMappings within a SubmodelConfiguration"""
    model = FieldMapping
    extra = 0
    fields = ('submodel_element', 'jsonpath_expression', 'default_value', 'order')
    readonly_fields = ('id',)
    ordering = ('order',)
    autocomplete_fields = ['submodel_element']


class SubmodelConfigurationInline(admin.TabularInline):
    """Inline editor for SubmodelConfigurations within an AASConnection"""
    model = SubmodelConfiguration
    extra = 0
    fields = ('entity_type', 'template', 'is_enabled', 'priority')
    readonly_fields = ('id',)
    ordering = ('entity_type', 'priority')
    show_change_link = True


@admin.register(AASConnection)
class AASConnectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'aas_api_url', 'is_active', 'auto_sync_enabled', 'is_default', 'last_tested', 'created')
    list_filter = ('is_active', 'auto_sync_enabled', 'is_default', 'created', 'last_modified')
    search_fields = ('name', 'description', 'aas_api_url')
    readonly_fields = ('created', 'last_modified', 'last_tested')
    inlines = [SubmodelConfigurationInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description')
        }),
        ('AAS Configuration', {
            'fields': ('aas_api_url', 'registry_api_url', 'discovery_api_url')
        }),
        ('Automatic Synchronization', {
            'fields': ('is_default', 'auto_sync_enabled', 'auto_delete_enabled'),
            'description': 'Configure automatic real-time synchronization of device changes to AAS'
        }),
        ('Keycloak OAuth2 (required for BaSyx 2.0)', {
            'fields': ('keycloak_server_url', 'keycloak_realm',
                       'keycloak_client_id', 'keycloak_client_secret'),
        }),
        ('Status', {
            'fields': ('is_active', 'created', 'last_modified', 'last_tested'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SubmodelTemplate)
class SubmodelTemplateAdmin(admin.ModelAdmin):
    """Admin interface for SubmodelTemplate"""
    list_display = ('id_short', 'name', 'idta_number', 'version', 'source_type', 'is_active', 'is_built_in', 'element_count')
    list_filter = ('source_type', 'is_active', 'is_built_in', 'created')
    search_fields = ('id_short', 'name', 'idta_number', 'template_id', 'semantic_id')
    readonly_fields = ('id', 'created', 'last_modified')
    inlines = [SubmodelElementInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('id_short', 'name', 'description')
        }),
        ('Identification', {
            'fields': ('template_id', 'idta_number', 'semantic_id', 'supplemental_semantic_ids')
        }),
        ('Versioning', {
            'fields': ('version', 'revision')
        }),
        ('Source & Status', {
            'fields': ('source_type', 'is_active', 'is_built_in')
        }),
        ('Configuration', {
            'fields': ('applicable_entity_types',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created', 'last_modified'),
            'classes': ('collapse',)
        }),
    )

    def element_count(self, obj):
        """Display count of elements in this template"""
        count = obj.elements.count()
        return format_html('<strong>{}</strong> elements', count)
    element_count.short_description = 'Elements'

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of built-in templates"""
        if obj and obj.is_built_in:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(SubmodelElement)
class SubmodelElementAdmin(admin.ModelAdmin):
    """Admin interface for SubmodelElement"""
    list_display = ('id_short', 'template', 'element_type', 'parent_element', 'semantic_id', 'cardinality', 'order')
    list_filter = ('element_type', 'cardinality', 'template')
    search_fields = ('id_short', 'semantic_id', 'template__id_short')
    readonly_fields = ('id',)
    autocomplete_fields = ['template', 'parent_element']

    fieldsets = (
        ('Basic Information', {
            'fields': ('template', 'parent_element', 'id_short', 'element_type', 'order')
        }),
        ('Display', {
            'fields': ('display_name', 'description')
        }),
        ('Semantic Information', {
            'fields': ('semantic_id', 'supplemental_semantic_ids')
        }),
        ('Type & Constraints', {
            'fields': ('value_type', 'cardinality', 'category')
        }),
        ('Additional Configuration', {
            'fields': ('qualifiers',),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('template', 'parent_element')


@admin.register(SubmodelConfiguration)
class SubmodelConfigurationAdmin(admin.ModelAdmin):
    """Admin interface for SubmodelConfiguration"""
    list_display = ('connection', 'entity_type', 'template', 'is_enabled', 'priority', 'mapping_count')
    list_filter = ('entity_type', 'is_enabled', 'connection')
    search_fields = ('connection__name', 'template__id_short')
    readonly_fields = ('id', 'created', 'last_modified')
    autocomplete_fields = ['connection', 'template']
    inlines = [FieldMappingInline]

    fieldsets = (
        ('Configuration', {
            'fields': ('connection', 'entity_type', 'template')
        }),
        ('Settings', {
            'fields': ('is_enabled', 'priority')
        }),
        ('Metadata', {
            'fields': ('id', 'created', 'last_modified'),
            'classes': ('collapse',)
        }),
    )

    def mapping_count(self, obj):
        """Display count of field mappings"""
        count = obj.field_mappings.count()
        if count == 0:
            return format_html('<span style="color: orange;">⚠ {} mappings</span>', count)
        return format_html('<strong>{}</strong> mappings', count)
    mapping_count.short_description = 'Mappings'

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('connection', 'template')


@admin.register(FieldMapping)
class FieldMappingAdmin(admin.ModelAdmin):
    """Admin interface for FieldMapping"""
    list_display = ('submodel_element', 'configuration', 'expression_preview', 'order')
    list_filter = ('is_multilanguage', 'configuration__entity_type')
    search_fields = ('jsonpath_expression', 'configuration__template__id_short', 'submodel_element__id_short')
    readonly_fields = ('id',)
    autocomplete_fields = ['configuration', 'submodel_element']

    fieldsets = (
        ('Target', {
            'fields': ('configuration', 'submodel_element', 'order')
        }),
        ('Mapping Definition', {
            'fields': ('jsonpath_expression',)
        }),
        ('Defaults & Validation', {
            'fields': ('default_value',)
        }),
        ('Transformations', {
            'fields': ('transform_function',),
            'classes': ('collapse',)
        }),
        ('Multi-language', {
            'fields': ('is_multilanguage', 'language_code'),
            'classes': ('collapse',)
        }),
    )

    def expression_preview(self, obj):
        """Display preview of expression"""
        if obj.jsonpath_expression:
            return format_html('<code>{}</code>', obj.jsonpath_expression[:50])
        elif obj.default_value:
            return format_html('<em>Default: {}</em>', obj.default_value[:50])
        return '-'
    expression_preview.short_description = 'Expression'

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('configuration', 'configuration__template', 'submodel_element')


@admin.register(EntityTypeConfiguration)
class EntityTypeConfigurationAdmin(admin.ModelAdmin):
    """Admin interface for EntityTypeConfiguration"""
    list_display = ('entity_type_label', 'connection', 'content_type', 'is_enabled', 'builder_class')
    list_filter = ('is_enabled', 'connection')
    search_fields = ('entity_type_label', 'connection__name', 'builder_class')
    readonly_fields = ('id', 'created', 'last_modified')
    autocomplete_fields = ['connection']

    fieldsets = (
        ('Configuration', {
            'fields': ('connection', 'content_type', 'entity_type_label')
        }),
        ('Settings', {
            'fields': ('is_enabled', 'builder_class', 'select_related_fields')
        }),
        ('Metadata', {
            'fields': ('id', 'created', 'last_modified'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('connection', 'content_type')

