def is_owner(request):
    return request.user.is_owner


def can_manage(request):
    return request.user.can_manage
