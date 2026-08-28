import requests
import logging
import json

from django import forms
from django.shortcuts import get_object_or_404
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.views.decorators.http import require_http_methods
from django.urls import reverse_lazy
from django.utils.timezone import now
from django.forms.models import BaseModelForm

from django.apps import apps

from aas_integration.models import (
    AASConnection,
    SubmodelConfiguration,
    SubmodelTemplate,
    SubmodelElement,
    FieldMapping,
    VALID_ENTITY_TYPES,
    AASSyncModes
)
from aas_integration.logging_utils import sanitize_for_log

from aas_integration.services import (
    SyncParams,
    SyncObject,
    create_sync_results_template,
    create_type_results_template,
    finalize_sync_results,
)

from .defaults import (TIMEOUT_LONG,
                      TIMEOUT_SHORT,
                      BASE_URL_DEFAULT,
                      URN_NAMESPACE_DEFAULT)

def get_model_class(model_import_path: str) -> type:
    """
    Get Django model class from import path using Django's apps registry.

    Args:
        model_import_path: Full path to model (e.g., 'dcim.models.Device')

    Returns:
        The model class

    Raises:
        ValueError: If the path format is invalid
        LookupError: If the model doesn't exist
    """
    # Parse 'dcim.models.Device' into app_label='dcim', model_name='Device'
    parts = model_import_path.split('.')
    if len(parts) >= 3 and parts[-2] == 'models':
        app_label = parts[-3]
        model_name = parts[-1]
    else:
        raise ValueError(f"Invalid model import path format: {model_import_path}")

    return apps.get_model(app_label, model_name)


logger = logging.getLogger(__name__)

def display_errors(form: BaseModelForm,request: HttpRequest, model_name: str) -> None:
    """
    Display error messages raised from validating fields of a model, or a generic error
    message if no corresponding field is found.

    Args:
        form: form containing the errors
        request: corresponding http request to be handed over to the message handler
        model_name: name of the model where the errors were raised
    Returns:
        None
    Raises:
        None
    """

    for error in form.errors:
        error_field = form.fields.get(error)
        if error_field:
            error_message = f'Input for {error_field.label} is invalid' 
        else:
            error_message = f'An error occurred while saving the changes for {model_name}'
        logger.error(error_message)
        messages.error(request,error_message)

class AASConnectionListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """List all AAS connections"""
    model = AASConnection
    template_name = 'aas_integration/aas_connection_list.html'
    context_object_name = 'connections'
    paginate_by = 25

    def test_func(self):
        return self.request.user.is_superuser


class AASConnectionDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View detail of a single AAS connection"""
    model = AASConnection
    template_name = 'aas_integration/aas_connection_detail.html'
    context_object_name = 'connection'

    def test_func(self):
        return self.request.user.is_superuser


class AASConnectionCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create a new AAS connection"""
    model = AASConnection
    template_name = 'aas_integration/aas_connection_form.html'
    fields = [
        'name', 'description', 'aas_api_url', 'registry_api_url', 'discovery_api_url',
        'aas_ui_url','is_active', 'auto_sync_enabled', 'auto_delete_enabled', 'is_default',
        'keycloak_server_url', 'keycloak_realm',
        'keycloak_client_id', 'keycloak_client_secret','aas_id_field', 'aas_link'
    ]
    success_url = reverse_lazy('plugins:aas_integration:aasconnection_list')

    def test_func(self):
        return self.request.user.is_superuser
    
    def form_invalid(self, form):
        display_errors(form,self.request,AASConnection._meta.verbose_name_raw)
        return super().form_invalid(form)

    def form_valid(self, form):
        messages.success(self.request, 'AAS Connection created successfully.')
        return super().form_valid(form)


class AASConnectionUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Update an existing AAS connection"""
    model = AASConnection
    template_name = 'aas_integration/aas_connection_form.html'
    fields = [
        'name', 'description', 'aas_api_url', 'registry_api_url', 'discovery_api_url', 
        'aas_ui_url', 'is_active', 'auto_sync_enabled', 'auto_delete_enabled', 'is_default',
        'keycloak_server_url', 'keycloak_realm',
        'keycloak_client_id', 'keycloak_client_secret','aas_id_field','aas_link'
    ]
    success_url = reverse_lazy('plugins:aas_integration:aasconnection_list')

    def test_func(self):
        return self.request.user.is_superuser
    
    def form_invalid(self, form):
        display_errors(form,self.request,AASConnection._meta.verbose_name_raw)
        return super().form_invalid(form)

    def form_valid(self, form):
        messages.success(self.request, 'AAS Connection updated successfully.')
        return super().form_valid(form)


class AASConnectionDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete an AAS connection"""
    model = AASConnection
    template_name = 'aas_integration/aas_connection_confirm_delete.html'
    success_url = reverse_lazy('plugins:aas_integration:aasconnection_list')

    def test_func(self):
        return self.request.user.is_superuser

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'AAS Connection deleted successfully.')
        return super().delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["GET"])
def test_connection(request: HttpRequest, pk: int) -> JsonResponse:
    """Testing given AAS connection by retrieving shells from the repository API"""
    connection = get_object_or_404(AASConnection, pk=pk)
    
    try:
        url = f'{connection.aas_api_url}/shells'
        
        headers = connection.get_auth_headers()
        
        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )
        
        match response.status_code:
            case 200:
                data = response.json()
                shells = data.get("result", [])
                connection.last_tested = now()
                connection.save()
                return JsonResponse({
                    'success': True,
                    'message': f'Connected! Found {len(shells)} shells.'
                })
            case _:
                logger.error(f'AAS connection test failed for {sanitize_for_log(connection.name)}: HTTP {response.status_code}')
                return JsonResponse({
                    'success': False,
                    'message': 'Connection failed. See logs for details.'
                })
    except requests.exceptions.ConnectionError:
        logger.exception(f'AAS connection error for {sanitize_for_log(connection.name)}.')
        return JsonResponse({
            'success': False,
            'message': 'Connection error: Cannot reach AAS server'
        })
    except requests.exceptions.Timeout:
        logger.exception(f'AAS connection timeout for {sanitize_for_log(connection.name)}.')
        return JsonResponse({
            'success': False,
            'message': 'Connection error: Timed out.'
        })
    except (requests.RequestException, ValueError):
        logger.exception(f'Error testing AAS connection {sanitize_for_log(connection.name)}.')

        return JsonResponse({
            'success': False,
            'message': 'Error occurred while testing connection'
        })


class AASSyncView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """View for syncing NetBox assets to AAS"""
    template_name = 'aas_integration/aas_sync.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Build dynamic counts from database configuration
        # Map entity_type to model path
        entity_type_models = {
            'devices': ('dcim.models.Device', 'Devices', ['device_type', 'device_type__manufacturer']),
            'racks': ('dcim.models.Rack', 'Racks', ['rack_type', 'rack_type__manufacturer', 'site', 'location']),
        }

        sync_counts = {}
        total_objects = 0

        # Get unique entity types from enabled configurations (with fallback to global defaults)
        active_connection = AASConnection.objects.filter(is_active=True).first()
        if active_connection:
            # Get all entity types that have configurations (connection-specific OR global)
            # Check connection-specific first
            connection_entity_types = SubmodelConfiguration.objects.filter(
                connection=active_connection,
                is_enabled=True
            ).values_list('entity_type', flat=True).distinct()

            # Get global default entity types
            global_entity_types = SubmodelConfiguration.objects.filter(
                connection=None,
                is_enabled=True
            ).values_list('entity_type', flat=True).distinct()

            # Combine both (connection-specific takes priority, but we show counts for all)
            enabled_entity_types = set(connection_entity_types) | set(global_entity_types)

            for entity_type in enabled_entity_types:
                if entity_type not in VALID_ENTITY_TYPES:
                    logger.warning(f"Skipping unsupported entity_type from database: {sanitize_for_log(entity_type)}")
                    continue

                if entity_type in entity_type_models:
                    model_import, label, _ = entity_type_models[entity_type]
                    model_class = get_model_class(model_import)

                    count = model_class.objects.count()
                    sync_counts[entity_type] = {
                        'label': label,
                        'count': count
                    }
                    total_objects += count

        context['sync_counts'] = sync_counts
        context['total_objects'] = total_objects
        context['connections'] = AASConnection.objects.filter(is_active=True)
        context['sync_modes'] = AASSyncModes.SYNC_MODE_DESC
        context['default_base_url'] = BASE_URL_DEFAULT
        context['default_urn_namespace'] = URN_NAMESPACE_DEFAULT

        return context


def _extract_sync_params(request: HttpRequest):
    """Extract and validate sync parameters from request."""
    connection_id = request.POST.get('connection_id')
    base_url = request.POST.get('base_url', 'netbox.local').strip()
    urn_namespace = request.POST.get('urn_namespace', 'apeirora.eu').strip()
    sync_mode = request.POST.get('sync_mode', AASSyncModes.MERGE).strip()

    if not connection_id:
        return None, JsonResponse({'success': False, 'message': 'No AAS connection selected'})

    if not base_url:
        return None, JsonResponse({'success': False, 'message': 'Base URL is required'})

    connection = get_object_or_404(AASConnection, pk=connection_id, is_active=True)

    return {
        'connection': connection,
        'base_url': base_url,
        'urn_namespace': urn_namespace,
        'sync_mode': sync_mode
    }, None


def _sync_single_type(config, connection, sync_params, overall_results):
    """Sync all objects of a single type and update results using AASShellBuilder."""
    object_type = config['type']
    label = config['label']
    model_class = get_model_class(config['model_import'])

    # Query objects with optional select_related
    queryset = model_class.objects.all()
    if select_related := config.get('select_related'):
        queryset = queryset.select_related(*select_related)

    type_results = create_type_results_template()
    type_results['total'] = queryset.count()

    # Sync each object using UnifiedAASBuilder (no builder_func needed)
    for obj in queryset:
        sync_obj = SyncObject(obj=obj, connection=connection, sync_params=sync_params)
        result = sync_obj.sync_entity_to_aas_repo()

        if result.success:
            type_results['created'] += 1
        else:
            type_results['failed'] += 1
            type_results['errors'].append(f"{result.asset_name}: {result.error}")

    # Update overall results
    overall_results['by_type'][object_type] = {
        'label': label,
        'created': type_results['created'],
        'failed': type_results['failed'],
        'total': type_results['total'],
        'errors': type_results['errors']
    }
    overall_results['total_created'] += type_results['created']
    overall_results['total_failed'] += type_results['failed']


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
def sync_assets_to_aas(request: HttpRequest) -> JsonResponse:
    """
    Unified sync endpoint that handles all NetBox asset types to AAS repository.

    Flow:
    1. Run validation as first step
    2. If validation issues found, return them for user resolution
    3. If user provided resolutions, apply them
    4. Proceed with sync only after validation passes
    """
    entity_type_config = {
        'devices': {
            'label': 'Devices',
            'model_import': 'dcim.models.Device',
            'select_related': ['device_type', 'device_type__manufacturer', 'site', 'rack']
        },
        'racks': {
            'label': 'Racks',
            'model_import': 'dcim.models.Rack',
            'select_related': ['rack_type', 'rack_type__manufacturer', 'site', 'location']
        },
    }

    try:
        params, error_response = _extract_sync_params(request)
        if error_response:
            return error_response

        validation_passed, validation_response = SyncObject.handle_pre_sync_validation()
        if not validation_passed:
            return JsonResponse(validation_response)

        sync_params = SyncParams(
            base_url=params['base_url'],
            urn_namespace=params['urn_namespace'],
            sync_mode=params['sync_mode'],
            aasx_upload_timeout=TIMEOUT_LONG,
            submodel_reference_timeout=TIMEOUT_SHORT,
            test_connection_timeout=TIMEOUT_SHORT
        )

        overall_results = create_sync_results_template()

        # Get enabled entity types with fallback to global defaults
        connection_entity_types = SubmodelConfiguration.objects.filter(
            connection=params['connection'],
            is_enabled=True
        ).values_list('entity_type', flat=True).distinct()

        global_entity_types = SubmodelConfiguration.objects.filter(
            connection=None,
            is_enabled=True
        ).values_list('entity_type', flat=True).distinct()

        # Combine both (connection-specific takes priority if it exists)
        enabled_entity_types = set(connection_entity_types) | set(global_entity_types)

        for entity_type in enabled_entity_types:
            if entity_type not in VALID_ENTITY_TYPES:
                logger.warning(f"Skipping unsupported entity_type from database: {sanitize_for_log(entity_type)}")
                continue

            if entity_type in entity_type_config:
                config = {
                    'type': entity_type,
                    **entity_type_config[entity_type]
                }
                _sync_single_type(config, params['connection'], sync_params, overall_results)

        return JsonResponse(finalize_sync_results(overall_results))

    except Exception:
        logger.exception('Error during sync')
        return JsonResponse({'success': False, 'message': 'Sync failed'})


def _validate_single_object(obj, object_type):
    """Validate a single object and return validation status and reason."""
    if object_type == 'devices':
        if not obj.device_type:
            return False, "No device type"
        if not obj.device_type.manufacturer:
            return False, "No manufacturer"
    elif object_type == 'racks':
        if not obj.rack_type:
            return False, "No rack type"
        if not obj.rack_type.manufacturer:
            return False, "No manufacturer"
    return True, None


def _validate_objects_for_type(config):
    """Validate all objects for a given type configuration."""
    object_type = config['type']
    label = config['label']
    model_class = get_model_class(config['model_import'])
    
    # Query objects with optional select_related
    queryset = model_class.objects.all()
    if select_related := config.get('select_related'):
        queryset = queryset.select_related(*select_related)
    
    total_count = queryset.count()
    complete_count = 0
    incomplete_count = 0
    missing_reasons = {}
    
    for obj in queryset:
        is_valid, reason = _validate_single_object(obj, object_type)
        if is_valid:
            complete_count += 1
        else:
            incomplete_count += 1
            missing_reasons[reason] = missing_reasons.get(reason, 0) + 1
    
    return {
        'label': label,
        'total': total_count,
        'complete': complete_count,
        'incomplete': incomplete_count,
        'missing_reasons': missing_reasons,
        'needs_defaults': incomplete_count > 0
    }


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["GET"])
def validate_sync_data(request: HttpRequest) -> JsonResponse:
    """
    Validate data availability before sync - dry run to check what's missing.
    Returns statistics about objects with complete vs incomplete data.
    """
    entity_type_config = {
        'devices': {
            'label': 'Devices',
            'model_import': 'dcim.models.Device',
            'select_related': ['device_type', 'device_type__manufacturer']
        },
        'racks': {
            'label': 'Racks',
            'model_import': 'dcim.models.Rack',
            'select_related': ['rack_type', 'rack_type__manufacturer', 'site', 'location']
        },
    }

    try:
        validation_results = {
            'success': True,
            'by_type': {},
            'has_missing_data': False,
            'message': ''
        }

        active_connection = AASConnection.objects.filter(is_active=True).first()
        if not active_connection:
            return JsonResponse({
                'success': False,
                'message': 'No active AAS connection found'
            })

        # Get enabled entity types with fallback to global defaults
        connection_entity_types = SubmodelConfiguration.objects.filter(
            connection=active_connection,
            is_enabled=True
        ).values_list('entity_type', flat=True).distinct()

        global_entity_types = SubmodelConfiguration.objects.filter(
            connection=None,
            is_enabled=True
        ).values_list('entity_type', flat=True).distinct()

        enabled_entity_types = set(connection_entity_types) | set(global_entity_types)

        for entity_type in enabled_entity_types:
            if entity_type not in VALID_ENTITY_TYPES:
                logger.warning(f"Skipping unsupported entity_type from database: {sanitize_for_log(entity_type)}")
                continue

            if entity_type in entity_type_config:
                config = {
                    'type': entity_type,
                    **entity_type_config[entity_type]
                }
                type_result = _validate_objects_for_type(config)
                validation_results['by_type'][entity_type] = type_result

                if type_result['incomplete'] > 0:
                    validation_results['has_missing_data'] = True

        validation_results['message'] = (
            'Some objects are missing required data. You can provide default values or skip them.'
            if validation_results['has_missing_data']
            else 'All objects have complete data and are ready to sync.'
        )
        
        return JsonResponse(validation_results)

    except Exception:
        logger.exception('Error validating sync data')
        return JsonResponse({'success': False, 'message': 'Validation failed'}, status=500)

class SubmodelTemplateListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """List view for SubmodelTemplates"""
    model = SubmodelTemplate
    template_name = 'aas_integration/submodeltemplate_list.html'
    context_object_name = 'templates'

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return SubmodelTemplate.objects.all().order_by('id_short')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add element counts for each template
        for template in context['templates']:
            template.element_count = template.elements.count()
            template.config_count = SubmodelConfiguration.objects.filter(template=template).count()
        return context


class SubmodelTemplateDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Detail view for a single SubmodelTemplate"""
    model = SubmodelTemplate
    template_name = 'aas_integration/submodeltemplate_detail.html'
    context_object_name = 'template'

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        template = self.object

        # Get root elements (no parent)
        context['root_elements'] = template.elements.filter(parent_element=None).order_by('order')

        # Get all configurations using this template
        context['configurations'] = SubmodelConfiguration.objects.filter(
            template=template
        ).select_related('connection').order_by('connection__name', 'entity_type')

        return context


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
def delete_submodel_template(request, pk):
    """Delete a non-built-in submodel template"""
    from django.shortcuts import redirect

    template = get_object_or_404(SubmodelTemplate, pk=pk)

    if template.is_built_in:
        messages.error(request, f'Cannot delete built-in template: {template.name}')
    else:
        template_name = template.name
        template.delete()  # CASCADE will delete elements and configurations
        messages.success(request, f'Successfully deleted template: {template_name}')

    return redirect('plugins:aas_integration:submodeltemplate_list')


class SubmodelConfigurationListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """List view for SubmodelConfigurations"""
    model = SubmodelConfiguration
    template_name = 'aas_integration/submodelconfiguration_list.html'
    context_object_name = 'configurations'

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return SubmodelConfiguration.objects.select_related(
            'connection', 'template'
        ).prefetch_related('field_mappings').order_by(
            'connection__name', 'entity_type', 'priority'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Separate global and connection-specific configs
        context['global_configs'] = [c for c in context['configurations'] if c.connection is None]
        context['connection_configs'] = [c for c in context['configurations'] if c.connection is not None]

        # Add mapping counts
        for config in context['configurations']:
            config.mapping_count = config.field_mappings.count()

        return context


class SubmodelConfigurationForm(forms.ModelForm):
    """Custom form for SubmodelConfiguration with dynamic entity_type choices"""

    # Declare entity_type explicitly to override model field
    entity_type = forms.ChoiceField(
        required=True,
        label='Entity Type',
        help_text='Which NetBox entity type should this template apply to?'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get DCIM entity types for dropdown
        dcim_types = ContentType.objects.filter(app_label='dcim').order_by('model')
        entity_choices = [('', 'Select entity type...')]

        for ct in dcim_types:
            model_name = f"{ct.app_label}.{ct.model}"
            label = ct.model.replace('_', ' ').title()
            if ct.model == 'device':
                entity_choices.insert(1, (model_name, label))
            elif ct.model == 'rack':
                entity_choices.insert(2 if len(entity_choices) > 1 else 1, (model_name, label))
            else:
                entity_choices.append((model_name, label))

        # Set the choices
        self.fields['entity_type'].choices = entity_choices
        self.fields['entity_type'].widget.choices = entity_choices  # Also set on widget

        # Configure connection field
        self.fields['connection'].required = False
        self.fields['connection'].empty_label = 'Global Default (applies to all connections)'

    class Meta:
        model = SubmodelConfiguration
        fields = ['connection', 'is_enabled', 'priority']  # Exclude entity_type to avoid ModelForm generating it


class SubmodelConfigurationCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = SubmodelConfiguration
    form_class = SubmodelConfigurationForm
    template_name = 'aas_integration/submodelconfiguration_form.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_initial(self):
        """Pre-populate template from URL parameter"""
        initial = super().get_initial()
        initial['is_enabled'] = True
        initial['priority'] = 100
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        template_id = self.kwargs.get('template_id')
        if template_id:
            context['template'] = get_object_or_404(SubmodelTemplate, pk=template_id)

        return context

    def form_valid(self, form):
        template_id = self.kwargs.get('template_id')
        if template_id:
            form.instance.template = get_object_or_404(SubmodelTemplate, pk=template_id)

        messages.success(self.request, f'Successfully created mapping configuration for {form.instance.template.name}')
        return super().form_valid(form)

    def get_success_url(self):
        return f'/plugins/aas-integration/configurations/{self.object.pk}/'


class SubmodelConfigurationDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Detail view for a single SubmodelConfiguration"""
    model = SubmodelConfiguration
    template_name = 'aas_integration/submodelconfiguration_detail.html'
    context_object_name = 'configuration'

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = self.object

        top_level_elements = config.template.elements.filter(
            parent_element=None
        ).order_by('order')

        existing_mappings = {
            mapping.submodel_element_id: mapping
            for mapping in config.field_mappings.select_related('submodel_element').all()
        }

        def build_element_tree(element, depth=0):
            """Recursively build element tree with nesting information"""
            mapping = existing_mappings.get(element.id)
            item = {
                'element': element,
                'mapping': mapping,
                'is_mapped': mapping is not None,
                'is_element_required': element.cardinality in ['One', 'OneToMany'],
                'depth': depth,
                'is_collection': element.element_type in ['SubmodelElementCollection', 'SubmodelElementList'],
            }

            result = [item]

            if item['is_collection']:
                children = element.child_elements.order_by('order')
                for child in children:
                    result.extend(build_element_tree(child, depth + 1))

            return result

        elements_with_status = []
        for element in top_level_elements:
            elements_with_status.extend(build_element_tree(element))

        # Count only mappable elements (not collections themselves)
        mappable_elements = [item for item in elements_with_status if not item['is_collection']]

        context['elements_with_status'] = elements_with_status
        context['mapped_count'] = sum(1 for item in mappable_elements if item['is_mapped'])
        context['total_mappable'] = len(mappable_elements)
        context['required_unmapped_count'] = sum(
            1 for item in mappable_elements
            if item['is_element_required'] and not item['is_mapped']
        )

        return context


class SubmodelConfigurationUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Update view for SubmodelConfiguration"""
    model = SubmodelConfiguration
    form_class = SubmodelConfigurationForm
    template_name = 'aas_integration/submodelconfiguration_form.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['template'] = self.object.template
        context['is_edit'] = True
        return context

    def form_valid(self, form):
        messages.success(self.request, f'Successfully updated mapping configuration for {form.instance.template.name}')
        return super().form_valid(form)

    def get_success_url(self):
        return f'/plugins/aas-integration/configurations/{self.object.pk}/'


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
def delete_submodel_configuration(request, pk):
    """Delete a submodel configuration"""
    from django.shortcuts import redirect

    config = get_object_or_404(SubmodelConfiguration, pk=pk)
    config_name = f"{config.template.name} for {config.entity_type}"
    config.delete()
    messages.success(request, f'Successfully deleted mapping configuration: {config_name}')

    return redirect('plugins:aas_integration:submodelconfiguration_list')


class FieldMappingForm(forms.ModelForm):

    class Meta:
        model = FieldMapping
        fields = [
            'submodel_element',
            'jsonpath_expression',
            'default_value',
            'transform_function',
            'is_multilanguage', 'language_code',
            'order'
        ]
        widgets = {
            'jsonpath_expression': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        configuration = kwargs.pop('configuration', None)
        super().__init__(*args, **kwargs)

        # Filter submodel_element to only show elements from the template
        if configuration:
            self.fields['submodel_element'].queryset = SubmodelElement.objects.filter(
                template=configuration.template
            ).order_by('parent_element__id_short', 'order', 'id_short')


class FieldMappingCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = FieldMapping
    form_class = FieldMappingForm
    template_name = 'aas_integration/fieldmapping_form.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        config_id = self.kwargs.get('config_id')
        kwargs['configuration'] = get_object_or_404(SubmodelConfiguration, pk=config_id)
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        # Pre-populate submodel_element from query parameter
        element_id = self.request.GET.get('element')
        if element_id:
            initial['submodel_element'] = element_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config_id = self.kwargs.get('config_id')
        context['configuration'] = get_object_or_404(SubmodelConfiguration, pk=config_id)
        # Pass the element_id to template so we can make the field readonly
        element_id = self.request.GET.get('element')
        if element_id:
            context['preselected_element'] = element_id
        return context

    def form_valid(self, form):
        config_id = self.kwargs.get('config_id')
        form.instance.configuration = get_object_or_404(SubmodelConfiguration, pk=config_id)

        messages.success(self.request, f'Successfully created field mapping')
        return super().form_valid(form)

    def get_success_url(self):
        return f'/plugins/aas-integration/configurations/{self.kwargs.get("config_id")}/'


class FieldMappingUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = FieldMapping
    form_class = FieldMappingForm
    template_name = 'aas_integration/fieldmapping_form.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['configuration'] = self.object.configuration
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['configuration'] = self.object.configuration
        context['is_edit'] = True
        return context

    def form_valid(self, form):
        messages.success(self.request, f'Successfully updated field mapping')
        return super().form_valid(form)

    def get_success_url(self):
        return f'/plugins/aas-integration/configurations/{self.object.configuration.pk}/'


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
def delete_field_mapping(request, pk):
    """Delete a field mapping"""
    from django.shortcuts import redirect

    mapping = get_object_or_404(FieldMapping, pk=pk)
    config_id = mapping.configuration.pk
    mapping.delete()
    messages.success(request, f'Successfully deleted field mapping')

    return redirect('plugins:aas_integration:submodelconfiguration_detail', pk=config_id)
