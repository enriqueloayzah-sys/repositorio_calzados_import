from django import forms
from django.contrib.auth.models import User
from .models import Calzado, VarianteCalzado, Promocion

class RegistroClienteForm(forms.Form):
    nombre_completo = forms.CharField(max_length=120, widget=forms.TextInput(attrs={'class': 'form-control'}))
    username = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    telefono = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), min_length=6)

    def clean_username(self):
        u = self.cleaned_data['username']
        if User.objects.filter(username=u).exists():
            raise forms.ValidationError("Ese nombre de usuario ya existe.")
        return u

class CalzadoForm(forms.ModelForm):
    class Meta:
        model = Calzado
        fields = ['categoria', 'marca', 'nombre', 'descripcion', 'precio_base', 'imagen', 'activo']
        widgets = {
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'precio_base': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'imagen': forms.FileInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class VarianteForm(forms.ModelForm):
    class Meta:
        model = VarianteCalzado
        fields = ['talla', 'color', 'stock']
        widgets = {
            'talla': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class PromocionForm(forms.ModelForm):
    class Meta:
        model = Promocion
        fields = ['calzado', 'titulo', 'porcentaje_descuento', 'fecha_inicio', 'fecha_fin', 'activa']
        widgets = {
            'calzado': forms.Select(attrs={'class': 'form-select'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'porcentaje_descuento': forms.NumberInput(attrs={'class': 'form-control'}),
            'fecha_inicio': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'fecha_fin': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
