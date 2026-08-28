"""Utilities for handling and formatting sync results."""


def create_sync_results_template() -> dict:
    """
    Create a template for aggregated sync results.

    Returns:
        Dictionary with empty sync results structure
    """
    return {
        'success': True,
        'partial_success': False,
        'total_created': 0,
        'total_failed': 0,
        'by_type': {},
        'message': ''
    }


def create_type_results_template() -> dict:
    """
    Create a template for per-type sync results.

    Returns:
        Dictionary with empty per-type results structure
    """
    return {
        'created': 0,
        'failed': 0,
        'total': 0,
        'errors': []
    }


def finalize_sync_results(overall_results: dict) -> dict:
    """
    Finalize sync results by setting overall success flags and message.

    Args:
        overall_results: Dictionary with sync results to finalize

    Returns:
        Updated overall_results dictionary
    """
    total_failed = overall_results['total_failed']
    total_created = overall_results['total_created']

    overall_results['success'] = total_failed == 0
    overall_results['partial_success'] = total_created > 0 and total_failed > 0

    if total_failed == 0:
        overall_results['message'] = f"Successfully synced {total_created} objects to AAS"
    elif total_created > 0 and total_failed > 0:
        overall_results['message'] = f"Partial success: {total_created} created, {total_failed} failed"
    else:
        overall_results['message'] = f"All syncs failed: {total_failed} failures"

    return overall_results
