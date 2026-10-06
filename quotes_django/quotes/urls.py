from django.urls import path

from . import views

app_name = 'quotes'

urlpatterns = [
    path('', views.index, name='index'),
    path('tag/<str:tag_name>/', views.quotes_by_tag, name='tag'),
    path('author/<int:author_id>/', views.author_detail, name='author'),
    path('add/author/', views.add_author, name='add_author'),
    path('add/quote/', views.add_quote, name='add_quote'),
    path('scrape/', views.scrape, name='scrape'),
]