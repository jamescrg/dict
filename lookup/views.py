from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from . import dict as dictionary

MAX_QUERY = 200


@never_cache
@require_GET
def index(request):
    return render(request, "lookup/index.html")


def manifest(request):
    """Web app manifest, so a home-screen shortcut gets the site's own icon and name."""
    icons = [{"src": static("lookup/icon-%d.png" % size), "sizes": "%dx%d" % (size, size),
              "type": "image/png", "purpose": purpose}
             for size in (192, 512) for purpose in ("any", "maskable")]
    return JsonResponse({
        "name": "Wörterbuch", "short_name": "Wörterbuch", "start_url": "/", "scope": "/",
        "display": "standalone", "background_color": "#282828", "theme_color": "#282828",
        "icons": icons,
    }, content_type="application/manifest+json")


@require_GET
def search(request):
    """?q=what was typed -> the form hints and entries for it (lookup/dict.py)."""
    return JsonResponse(dictionary.search(request.GET.get("q", "")[:MAX_QUERY]))


@require_GET
def line(request):
    """?id=line -> every sub-entry of that Ding line, as [German, English] pairs."""
    try:
        line_id = int(request.GET["id"])
    except (KeyError, ValueError):
        return HttpResponseBadRequest("bad request")
    return JsonResponse({"pairs": dictionary.line(line_id)})


@require_GET
def about(request):
    return JsonResponse({key: dictionary.meta(key) for key in ("ding_version", "lines", "forms")})
