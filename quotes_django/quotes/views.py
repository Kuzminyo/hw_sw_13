from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import AuthorForm, QuoteForm
from .models import Author, Quote, Tag
from .scraper import scrape_quotes

QUOTES_PER_PAGE = 10


def top_tags(limit=10):
    return (Tag.objects.annotate(num=Count('quotes'))
            .filter(num__gt=0).order_by('-num', 'name')[:limit])


def _quotes_page(request, queryset, extra=None):
    queryset = queryset.select_related('author').prefetch_related('tags')
    page = Paginator(queryset, QUOTES_PER_PAGE).get_page(request.GET.get('page'))
    context = {'page_obj': page, 'top_tags': top_tags()}
    context.update(extra or {})
    return render(request, 'quotes/index.html', context)


def index(request):
    return _quotes_page(request, Quote.objects.all())


def quotes_by_tag(request, tag_name):
    tag = get_object_or_404(Tag, name=tag_name)
    return _quotes_page(request, tag.quotes.all(), {'tag': tag})


def author_detail(request, author_id):
    author = get_object_or_404(Author, pk=author_id)
    return render(request, 'quotes/author.html', {'author': author})


@login_required
def add_author(request):
    form = AuthorForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        author = form.save(commit=False)
        author.created_by = request.user
        author.save()
        messages.success(request, f'Author "{author.fullname}" added.')
        return redirect('quotes:author', author_id=author.pk)
    return render(request, 'quotes/form.html', {'form': form, 'title': 'Add author'})


@login_required
def add_quote(request):
    form = QuoteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        quote = form.save(commit=False)
        quote.created_by = request.user
        quote.save()
        form.save_tags(quote)
        messages.success(request, 'Quote added.')
        return redirect('quotes:index')
    return render(request, 'quotes/form.html', {'form': form, 'title': 'Add quote'})


@login_required
@require_POST
def scrape(request):
    try:
        new_authors, new_quotes = scrape_quotes(user=request.user)
    except Exception as exc:  # network errors, changed page layout
        messages.error(request, f'Scraping failed: {exc}')
    else:
        messages.success(request, f'Scraping finished: {new_authors} new authors, {new_quotes} new quotes.')
    return redirect('quotes:index')