from django import forms

from .models import Author, Quote, Tag


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['fullname', 'born_date', 'born_location', 'description']
        widgets = {
            'born_date': forms.TextInput(attrs={'placeholder': 'March 14, 1879'}),
            'description': forms.Textarea(attrs={'rows': 6}),
        }


class QuoteForm(forms.ModelForm):
    tags = forms.CharField(
        required=False,
        help_text='Comma separated, e.g. life, love, humor',
    )

    class Meta:
        model = Quote
        fields = ['quote', 'author']
        widgets = {'quote': forms.Textarea(attrs={'rows': 4})}

    def save_tags(self, quote):
        names = {t.strip().lower() for t in self.cleaned_data['tags'].split(',') if t.strip()}
        quote.tags.set([Tag.objects.get_or_create(name=n)[0] for n in names])