from decimal import Decimal
from django.core.exceptions import ValidationError
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
            precio = self.precio_base - descuento
            return max(precio, Decimal('0.00')).quantize(Decimal('0.01'))
        return self.precio_base.quantize(Decimal('0.01'))

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

    def save(self, *args, **kwargs):
        if self.talla:
            self.talla = self.talla.strip()
        if self.color:
            self.color = self.color.strip().capitalize()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.calzado.nombre} | Talla {self.talla} | {self.color} (Stock: {self.stock})"


class Promocion(models.Model):
    calzado = models.ForeignKey(Calzado, on_delete=models.CASCADE, related_name='promociones')
    titulo = models.CharField(max_length=120)
    porcentaje_descuento = models.PositiveIntegerField()
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    activa = models.BooleanField(default=True)

    def clean(self):
        if self.porcentaje_descuento < 1 or self.porcentaje_descuento > 90:
            raise ValidationError("El porcentaje de descuento debe estar entre 1% y 90%.")
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError("La fecha de fin no puede ser anterior a la fecha de inicio.")

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
    ESTADOS_ENTREGA = (
        ('PENDIENTE', 'Pendiente de entrega'),
        ('ENTREGADO', 'Entregado'),
    )
    cliente = models.ForeignKey(User, on_delete=models.PROTECT, related_name='pedidos')
    codigo = models.CharField(max_length=20, unique=True)
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(max_length=15, choices=ESTADOS, default='CONFIRMADO')
    estado_entrega = models.CharField(max_length=15, choices=ESTADOS_ENTREGA, default='PENDIENTE')
    fecha_entrega = models.DateTimeField(blank=True, null=True)
    entregado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='entregas_realizadas'
    )

    def __str__(self):
        return f"{self.codigo} - {self.cliente.username} ({self.get_estado_entrega_display()})"


class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    variante = models.ForeignKey(VarianteCalzado, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return (Decimal(self.cantidad) * self.precio_unitario).quantize(Decimal('0.01'))