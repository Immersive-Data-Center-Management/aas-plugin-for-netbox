"""Serialization utilities for API responses."""


def serialize_validation_issues(issues: list) -> list:
    """
    Serialize ValidationIssue objects for JSON response.

    Args:
        issues: List of ValidationIssue objects

    Returns:
        List of serialized issue data for frontend
    """
    serialized_issues = []

    for issue in issues:
        object_names = [getattr(obj, 'name', str(obj)) for obj in issue.objects[:5]]

        # Add "and X more" if there are more than 5 objects
        if len(issue.objects) > 5:
            object_names.append(f"and {len(issue.objects) - 5} more")

        serialized_issue = {
            'issue_type': issue.issue_type,
            'object_type': issue.object_type,
            'description': issue.description,
            'object_count': len(issue.objects),
            'object_names': object_names,
            'resolution_options': issue.resolution_options
        }

        serialized_issues.append(serialized_issue)

    return serialized_issues
