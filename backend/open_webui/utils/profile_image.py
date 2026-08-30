"""Shared handling of `user.profile_image_url` on its way to a client.

Any feature that ships a user's avatar URL to the browser goes through
`sanitize_profile_image_url` so the placeholder defaults and the external-URL
forwarding policy are decided in exactly one place.
"""

from typing import Optional

from open_webui.env import ENABLE_PROFILE_IMAGE_URL_FORWARDING


def sanitize_profile_image_url(url, forward_external: Optional[bool] = None) -> str | None:
    # Only genuine custom images travel to the client: uploaded avatars are
    # data: URLs and OAuth pictures are http(s). The '/user.png' default and
    # the per-user '/api/v1/users/{id}/profile/image' placeholder both mean
    # "no upload" — mapped to None so the UI keeps its initials fallback.
    # External http(s) URLs additionally honour the same forwarding policy as
    # the profile-image endpoint: when forwarding is disabled the URL is
    # dropped so viewer browsers never fetch a third-party origin.
    #
    # `forward_external` defaults to the env flag; callers that hold their own
    # binding of it pass it explicitly.
    if forward_external is None:
        forward_external = ENABLE_PROFILE_IMAGE_URL_FORWARDING
    if url:
        if url.startswith('data:'):
            return url
        if url.startswith('http') and forward_external:
            return url
    return None
