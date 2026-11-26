from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class PerfilUsuario(models.Model):
    ROLES = (
        ('ADMIN', 'Administrador'),
        ('CLIENTE', 'Cliente'),
    )
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    rol = models.CharField(max_length=10, choices=ROLES, default='CLIENTE')
    telefono = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.usuario.username} ({self.get_rol_display()})"

class Categoria(models.Model):
    nombre = models.CharField(max_length=80, unique=True)

    class Meta:
        verbose_name_plural = "Categorías"

    def __str__(self):
        return self.nombre

class Calzado(models.Model):
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='calzados')
    marca = models.CharField(max_length=80)
    nombre = models.CharField(max_length=140)
    descripcion = models.TextField(blank=True)
    precio_base = models.DecimalField(max_digits=10, decimal_places=2)
    imagen = models.ImageField(upload_to='calzados/', blank=True, null=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def promocion_vigente(self):
        ahora = timezone.now()
        return self.promociones.filter(
            activa=True,
            fecha_inicio__lte=ahora,
            fecha_fin__gte=ahora
        ).order_by('-porcentaje_descuento').first()

    @property
    def precio_final(self):
        promo = self.promocion_vigente()
        if promo:
            descuento = (self.precio_base * Decimal(promo.porcentaje_descuento)) / Decimal('100')
            return (self.precio_base - descuento).quantize(Decimal('0.01'))
        return self.precio_base

    @property
    def stock_total(self):
        return sum(v.stock for v in self.variantes.all())

    def __str__(self):
        return f"{self.marca} - {self.nombre}"

class VarianteCalzado(models.Model):
    calzado = models.ForeignKey(Calzado, on_delete=models.CASCADE, related_name='variantes')
    talla = models.CharField(max_length=10)
    color = models.CharField(max_length=40)
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('calzado', 'talla', 'color')

    def __str__(self):
        return f"{self.calzado.nombre} | Talla {self.talla} | {self.color} (Stock: {self.stock})"

class Promocion(models.Model):
    calzado = models.ForeignKey(Calzado, on_delete=models.CASCADE, related_name='promociones')
    titulo = models.CharField(max_length=120)
    porcentaje_descuento = models.PositiveIntegerField()
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    activa = models.BooleanField(default=True)

    def esta_vigente(self):
        ahora = timezone.now()
        return self.activa and self.fecha_inicio <= ahora <= self.fecha_fin

    def __str__(self):
        return f"{self.titulo} (-{self.porcentaje_descuento}%)"

class Pedido(models.Model):
    ESTADOS = (
        ('CONFIRMADO', 'Confirmado / Vendido'),
        ('ANULADO', 'Anulado'),
    )
    cliente = models.ForeignKey(User, on_delete=models.PROTECT, related_name='pedidos')
    codigo = models.CharField(max_length=20, unique=True)
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(max_length=15, choices=ESTADOS, default='CONFIRMADO')

    def __str__(self):
        return f"{self.codigo} - {self.cliente.username}"

class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    variante = models.ForeignKey(VarianteCalzado, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario
