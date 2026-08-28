#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATASETS_DIR="${SCRIPT_DIR}/datasets"
GITHUB_RAW_BASE="https://raw.githubusercontent.com/netbox-community/netbox-demo-data/master/sql"

SOURCE_FILE=""
SKIP_PATCHES=false
SKIP_PLUGIN=false
DRY_RUN=false
CLEAN_MODE="full"

NETBOX_CONTAINER="netbox"
POSTGRES_CONTAINER="postgres"
DATABASE="netbox"
NETBOX_PORT="8085"

log_info() {
    echo "[INFO] $*"
}

log_success() {
    echo "[SUCCESS] $*"
}

log_warn() {
    echo "[WARN] $*"
}

log_error() {
    echo "[ERROR] $*"
}

print_header() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

usage() {
    cat << EOF
NetBox Demo Data Loader

Usage: $(basename "$0") COMMAND [OPTIONS]

Commands:
  download VERSION    Download netbox-demo-data SQL dump from GitHub
  load                Load SQL data into NetBox database
  clean [MODE]        Clean NetBox database
  status              Show current database statistics

Load Options:
  --source PATH       Path to SQL file (required for 'load')
  --skip-patches      Skip applying rack types patch
  --skip-plugin       Skip applying plugin setup (AAS connection)
  --dry-run           Preview operations without executing

Clean Modes:
  full               Full database reset - removes all data (default)
  preserve-plugin    Delete NetBox data but keep plugin tables

Examples:
  # Download and load NetBox v4.6 demo data
  $(basename "$0") download v4.6
  $(basename "$0") load --source datasets/netbox-demo-v4.6.sql

  # Load from custom dataset
  $(basename "$0") load --source /path/to/custom.sql

  # Clean database (full reset)
  $(basename "$0") clean full

  # Clean but preserve plugin configuration
  $(basename "$0") clean preserve-plugin

EOF
    exit 0
}

validate_prerequisites() {
    log_info "Validating prerequisites..."

    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running or not accessible"
        log_error "Please start Docker and try again"
        exit 1
    fi

    if ! command -v curl > /dev/null 2>&1; then
        log_error "Required command 'curl' is not installed"
        exit 1
    fi

    log_success "Prerequisites validated"
}

check_containers() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${NETBOX_CONTAINER}$"; then
        log_error "NetBox container '${NETBOX_CONTAINER}' is not running"
        log_error "Start it with: cd ${SCRIPT_DIR} && docker-compose up -d"
        exit 1
    fi

    if ! docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        log_error "PostgreSQL container '${POSTGRES_CONTAINER}' is not running"
        exit 1
    fi
}

confirm_action() {
    local message=$1
    echo ""
    echo "WARNING: ${message}"
    read -r -p "Are you sure you want to continue? [y/N] " response
    case "$response" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            log_info "Operation cancelled"
            exit 0
            ;;
    esac
}

cmd_download() {
    local version=$1

    if [ -z "$version" ]; then
        log_error "Version is required"
        echo "Usage: $(basename "$0") download VERSION"
        echo "Example: $(basename "$0") download v4.6"
        exit 1
    fi

    print_header "Downloading NetBox Demo Data: ${version}"

    mkdir -p "$DATASETS_DIR"

    local filename="netbox-demo-${version}.sql"
    local output_path="${DATASETS_DIR}/${filename}"
    local download_url="${GITHUB_RAW_BASE}/${filename}"

    # Check if file already exists
    if [ -f "$output_path" ]; then
        log_warn "File already exists: ${output_path}"
        confirm_action "This will overwrite the existing file."
    fi

    log_info "Downloading from: ${download_url}"
    log_info "Saving to: ${output_path}"

    if $DRY_RUN; then
        log_info "[DRY RUN] Would download: ${download_url}"
        return 0
    fi

    # Download with progress
    if curl -f -L --progress-bar -o "$output_path" "$download_url"; then
        local file_size
        file_size=$(du -h "$output_path" | cut -f1)
        log_success "Downloaded: ${filename} (${file_size})"
        log_info "Use 'load --source ${output_path}' to load this data"
    else
        log_error "Download failed"
        log_error "Please check the version exists at: ${GITHUB_RAW_BASE}/"
        rm -f "$output_path"
        exit 1
    fi
}

execute_sql_file() {
    local sql_file=$1

    log_info "Executing SQL from: $(basename "$sql_file")"

    if $DRY_RUN; then
        log_info "[DRY RUN] Would execute: ${sql_file} on ${DATABASE}"
        return 0
    fi

    if docker exec -i "$POSTGRES_CONTAINER" psql -U netbox -d "$DATABASE" < "$sql_file" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

apply_patches() {
    if $SKIP_PATCHES; then
        log_info "Skipping patches (--skip-patches)"
        return 0
    fi

    local patch_file="${SCRIPT_DIR}/netbox-demo-racktypes-patch.sql"

    if [ ! -f "$patch_file" ]; then
        log_warn "Patch file not found: ${patch_file}"
        return 0
    fi

    log_info "Applying rack types patch..."

    if $DRY_RUN; then
        log_info "[DRY RUN] Would apply patch: ${patch_file}"
        return 0
    fi

    if execute_sql_file "$patch_file"; then
        log_success "Patch applied successfully"
    else
        log_warn "Patch failed (non-critical, continuing)"
    fi
}

run_migrations() {
    log_info "Running Django migrations..."

    if $DRY_RUN; then
        log_info "[DRY RUN] Would run migrations in ${NETBOX_CONTAINER}"
        return 0
    fi

    # Run migrations - redirect both stdout and stderr to /dev/null, check only exit code
    if docker exec "$NETBOX_CONTAINER" bash -c "cd /opt/netbox/netbox && python manage.py migrate --noinput" >/dev/null 2>&1; then
        log_success "Migrations completed"
        return 0
    else
        log_error "Migrations failed"
        return 1
    fi
}

apply_plugin_setup() {
    if $SKIP_PLUGIN; then
        log_info "Skipping plugin setup (--skip-plugin)"
        return 0
    fi

    local setup_file="${SCRIPT_DIR}/aas-connection-setup.sql"

    if [ ! -f "$setup_file" ]; then
        log_warn "Plugin setup file not found: ${setup_file}"
        return 0
    fi

    log_info "Applying plugin setup (AAS connection)..."

    if $DRY_RUN; then
        log_info "[DRY RUN] Would apply setup: ${setup_file}"
        return 0
    fi

    if execute_sql_file "$setup_file"; then
        log_success "Plugin setup applied"
    else
        log_warn "Plugin setup failed (non-critical)"
    fi
}

restart_netbox() {
    log_info "Restarting NetBox container..."

    if $DRY_RUN; then
        log_info "[DRY RUN] Would restart: ${NETBOX_CONTAINER}"
        return 0
    fi

    docker restart "$NETBOX_CONTAINER" > /dev/null 2>&1

    # Wait for NetBox to be ready
    log_info "Waiting for NetBox to be ready..."

    local max_attempts=30
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${NETBOX_PORT}/api/" | grep -q "200\|401\|403"; then
            log_success "NetBox is ready"
            return 0
        fi
        sleep 1
        ((attempt++))
    done

    log_warn "NetBox may not be fully ready yet"
}

cmd_load() {
    print_header "Loading Demo Data into NetBox (dev)"

    validate_prerequisites
    check_containers

    if [ -z "$SOURCE_FILE" ]; then
        log_error "--source is required"
        echo "Usage: $(basename "$0") load --source PATH"
        exit 1
    fi

    if [ ! -f "$SOURCE_FILE" ]; then
        log_error "Source file not found: ${SOURCE_FILE}"
        exit 1
    fi

    log_info "Source file: ${SOURCE_FILE}"
    log_info "Database: ${DATABASE}"

    confirm_action "This will DROP and recreate the '${DATABASE}' database. All existing data will be lost!"

    log_info "Stopping NetBox container..."
    if ! $DRY_RUN; then
        docker stop "$NETBOX_CONTAINER" > /dev/null 2>&1
    fi

    log_info "Resetting database..."
    if ! $DRY_RUN; then
        docker exec "$POSTGRES_CONTAINER" psql -U postgres -c "DROP DATABASE IF EXISTS ${DATABASE};" > /dev/null 2>&1
        docker exec "$POSTGRES_CONTAINER" psql -U postgres -c "CREATE DATABASE ${DATABASE} OWNER netbox;" > /dev/null 2>&1
    fi

    log_info "Loading SQL dump (this may take 10-30 seconds)..."
    if ! execute_sql_file "$SOURCE_FILE"; then
        log_error "SQL load failed"
        log_error "Database may be in inconsistent state"
        exit 1
    fi
    log_success "SQL data loaded"

    log_info "Cleaning up any old plugin tables..."
    if ! $DRY_RUN; then
        docker exec "$POSTGRES_CONTAINER" psql -U netbox -d "$DATABASE" -c "
            DROP TABLE IF EXISTS aas_integration_submodeltemplate CASCADE;
            DROP TABLE IF EXISTS aas_integration_entitytypeconfiguration CASCADE;
            DROP TABLE IF EXISTS aas_integration_aasconnection CASCADE;
        " > /dev/null 2>&1
    fi

    apply_patches

    log_info "Starting NetBox container..."
    if ! $DRY_RUN; then
        docker start "$NETBOX_CONTAINER" > /dev/null 2>&1

        # Wait for NetBox to be ready for Django operations
        log_info "Waiting for NetBox to initialize..."
        sleep 10
    fi

    run_migrations

    apply_plugin_setup

    restart_netbox

    print_header "Load Complete!"

    echo "NetBox URL: http://localhost:${NETBOX_PORT}"
    echo "Login: admin / admin"
    echo ""
    echo "Use 'status' command to verify loaded data"
}

cmd_clean() {
    local mode="${1:-full}"

    if [ "$mode" != "full" ] && [ "$mode" != "preserve-plugin" ]; then
        log_error "Invalid clean mode: ${mode}"
        echo "Valid modes: full, preserve-plugin"
        exit 1
    fi

    print_header "Cleaning NetBox Database (dev, mode: ${mode})"

    validate_prerequisites
    check_containers

    if [ "$mode" = "full" ]; then
        confirm_action "This will DROP and recreate the '${DATABASE}' database. ALL data will be permanently deleted!"
    else
        confirm_action "This will delete NetBox data but preserve plugin tables in '${DATABASE}'."
    fi

    log_info "Stopping NetBox container..."
    if ! $DRY_RUN; then
        docker stop "$NETBOX_CONTAINER" > /dev/null 2>&1
    fi

    if [ "$mode" = "full" ]; then
        log_info "Performing full database reset..."
        if ! $DRY_RUN; then
            docker exec "$POSTGRES_CONTAINER" psql -U postgres -c "DROP DATABASE IF EXISTS ${DATABASE};" > /dev/null 2>&1
            docker exec "$POSTGRES_CONTAINER" psql -U postgres -c "CREATE DATABASE ${DATABASE} OWNER netbox;" > /dev/null 2>&1
        fi
    else
        log_info "Deleting NetBox data while preserving plugin tables..."
        if ! $DRY_RUN; then
            local cleanup_sql="
                DO \$\$
                DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (
                        SELECT tablename FROM pg_tables
                        WHERE schemaname = 'public'
                        AND tablename NOT LIKE 'aas_integration_%'
                        AND tablename NOT LIKE 'django_%'
                        AND tablename NOT LIKE 'auth_%'
                        AND tablename NOT LIKE 'users_%'
                    ) LOOP
                        EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE';
                    END LOOP;
                END \$\$;
            "
            echo "$cleanup_sql" | docker exec -i "$POSTGRES_CONTAINER" psql -U netbox -d "$DATABASE" > /dev/null 2>&1
        fi
    fi

    log_info "Starting NetBox container..."
    if ! $DRY_RUN; then
        docker start "$NETBOX_CONTAINER" > /dev/null 2>&1
        sleep 5
    fi

    run_migrations
    restart_netbox

    log_success "Database cleaned successfully"
}

cmd_status() {
    print_header "NetBox Database Status (dev)"

    validate_prerequisites
    check_containers

    log_info "Querying database statistics..."

    local query="
        SELECT
            (SELECT COUNT(*) FROM dcim_site) as sites,
            (SELECT COUNT(*) FROM dcim_manufacturer) as manufacturers,
            (SELECT COUNT(*) FROM dcim_devicetype) as device_types,
            (SELECT COUNT(*) FROM dcim_device) as devices,
            (SELECT COUNT(*) FROM dcim_rack) as racks,
            (SELECT COUNT(*) FROM ipam_ipaddress) as ip_addresses,
            (SELECT COUNT(*) FROM aas_integration_aasconnection) as aas_connections;
    "

    echo ""
    docker exec "$POSTGRES_CONTAINER" psql -U netbox -d "$DATABASE" -c "$query"
    echo ""
}

main() {
    if [ $# -eq 0 ]; then
        usage
    fi

    local command=$1
    shift

    # Handle download command specially (version comes before options)
    if [ "$command" = "download" ]; then
        if [ $# -eq 0 ]; then
            log_error "Version required for download"
            echo "Usage: $(basename "$0") download VERSION"
            exit 1
        fi
        local version=$1
        shift

        # Parse remaining options for download
        while [ $# -gt 0 ]; do
            case $1 in
                --dry-run)
                    DRY_RUN=true
                    shift
                    ;;
                -h|--help)
                    usage
                    ;;
                *)
                    log_error "Unknown option for download: $1"
                    usage
                    ;;
            esac
        done

        cmd_download "$version"
        exit 0
    fi

    # Handle clean command (mode comes before options)
    if [ "$command" = "clean" ]; then
        if [ $# -gt 0 ] && [[ ! "$1" =~ ^-- ]]; then
            CLEAN_MODE="$1"
            shift
        fi
    fi

    # Parse global options for other commands
    while [ $# -gt 0 ]; do
        case $1 in
            --source)
                SOURCE_FILE="$2"
                shift 2
                ;;
            --skip-patches)
                SKIP_PATCHES=true
                shift
                ;;
            --skip-plugin)
                SKIP_PLUGIN=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                usage
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                ;;
        esac
    done

    case $command in
        load)
            cmd_load
            ;;
        clean)
            cmd_clean "$CLEAN_MODE"
            ;;
        status)
            cmd_status
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown command: ${command}"
            usage
            ;;
    esac
}

main "$@"
