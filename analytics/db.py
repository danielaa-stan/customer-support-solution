"""PostgreSQL connections for a local process or a Docker service."""


def connect(url):
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    from psycopg.rows import dict_row
    options = {'autocommit': True, 'row_factory': dict_row, 'connect_timeout': 10}
    # Compose publishes only IPv4 loopback; avoid Windows' unreachable ::1 path.
    if conninfo_to_dict(url).get('host') == 'localhost':
        options['hostaddr'] = '127.0.0.1'
    return psycopg.connect(url, **options)
