from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .availability import with_availability
from .models import Part

@login_required
def part_list(request):
    query = request.GET.get("q", "").strip()
    parts = Part.objects.all()
    if query:
        parts = parts.filter(name__icontains=query)
    return render(request, "parts/list.html", {"parts": with_availability(parts), "query": query})
