def execute(sql, *params):
    """Stand-in for a database call."""
    return (sql, params)
