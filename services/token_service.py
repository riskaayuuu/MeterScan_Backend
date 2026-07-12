def calculate_usage(previous_token, current_token):

    usage = previous_token - current_token

    if usage < 0:
        usage = 0

    return round(usage, 2)