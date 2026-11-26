import uuid
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from .models import (
    PerfilUsuario, Categoria, Calzado, VarianteCalzado,
    Promocion, Pedido, DetallePedido
)
from .forms import RegistroClienteForm, CalzadoForm, VarianteForm, PromocionForm

def es_admin(user):
    return user.is_authenticated and hasattr(user, 'perfil') and user.perfil.rol == 'ADMIN'

def registro_view(request):
    if request.method == 'POST':
        form = RegistroClienteForm(request.POST)
        if form.is_valid():
            partes = form.cleaned_data['nombre_completo'].strip().split(' ', 1)
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=partes[0],
                last_name=partes[1] if len(partes) > 1 else ''
            )
            PerfilUsuario.objects.create(
                usuario=user,
                rol='CLIENTE',
                telefono=form.cleaned_data.get('telefono', '')
            )
            login(request, user)
            messages.success(request, "¡Cuenta creada exitosamente! Bienvenido a Calzados Import.")
            return redirect('catalogo')
    else:
        form = RegistroClienteForm()
    return render(request, 'tienda/registro.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        usuario_input = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=usuario_input, password=password)
        if user is not None:
            perfil, _ = PerfilUsuario.objects.get_or_create(
                usuario=user,
                defaults={'rol': 'ADMIN' if user.is_superuser else 'CLIENTE'}
            )
            login(request, user)
            if perfil.rol == 'ADMIN' or user.is_superuser:
                return redirect('panel_admin')
            return redirect('catalogo')
        messages.error(request, "Usuario o contraseña incorrectos.")
    return render(request, 'tienda/login.html')

def logout_view(request):
    logout(request)
    return redirect('catalogo')

def catalogo_view(request):
    categorias = Categoria.objects.all()
    calzados = Calzado.objects.filter(activo=True).prefetch_related('variantes', 'promociones')

    cat_id = request.GET.get('categoria')
    solo_ofertas = request.GET.get('ofertas')
    buscar = request.GET.get('q', '').strip()

    if cat_id:
        calzados = calzados.filter(categoria_id=cat_id)
    if buscar:
        calzados = calzados.filter(nombre__icontains=buscar) | calzados.filter(marca__icontains=buscar)

    items = []
    for c in calzados:
        promo = c.promocion_vigente()
        if solo_ofertas and not promo:
            continue
        items.append({
            'obj': c,
            'promo': promo,
            'precio_final': c.precio_final,
            'variantes_disponibles': c.variantes.filter(stock__gt=0),
        })

    carrito = request.session.get('carrito', {})
    total_items_carrito = sum(item['cantidad'] for item in carrito.values())

    return render(request, 'tienda/catalogo.html', {
        'items': items,
        'categorias': categorias,
        'total_items_carrito': total_items_carrito,
        'solo_ofertas': bool(solo_ofertas),
        'buscar': buscar,
    })

@login_required
def agregar_carrito(request, variante_id):
    if request.method == 'POST':
        variante = get_object_or_404(VarianteCalzado, id=variante_id)
        cantidad = int(request.POST.get('cantidad', 1))
        if cantidad < 1 or cantidad > variante.stock:
            messages.error(request, "Cantidad no válida o stock insuficiente.")
            return redirect('catalogo')

        carrito = request.session.get('carrito', {})
        key = str(variante.id)
        actual = carrito.get(key, {'cantidad': 0})['cantidad']
        if actual + cantidad > variante.stock:
            messages.error(request, "Supera el stock disponible para esa variante.")
            return redirect('catalogo')

        carrito[key] = {
            'variante_id': variante.id,
            'calzado_nombre': f"{variante.calzado.marca} {variante.calzado.nombre}",
            'talla': variante.talla,
            'color': variante.color,
            'precio': str(variante.calzado.precio_final),
            'cantidad': actual + cantidad,
        }
        request.session['carrito'] = carrito
        messages.success(request, "Producto agregado al carrito.")
    return redirect('ver_carrito')

@login_required
def ver_carrito(request):
    carrito = request.session.get('carrito', {})
    filas = []
    total = Decimal('0.00')
    for key, item in carrito.items():
        subtotal = Decimal(item['precio']) * item['cantidad']
        total += subtotal
        filas.append({**item, 'subtotal': subtotal})
    return render(request, 'tienda/carrito.html', {'filas': filas, 'total': total})

@login_required
def confirmar_pedido(request):
    if request.method != 'POST':
        return redirect('ver_carrito')

    carrito = request.session.get('carrito', {})
    if not carrito:
        messages.warning(request, "Tu carrito está vacío.")
        return redirect('catalogo')

    try:
        with transaction.atomic():
            pedido = Pedido.objects.create(
                cliente=request.user,
                codigo=f"CI-{uuid.uuid4().hex[:8].upper()}",
                total=Decimal('0.00'),
                estado='CONFIRMADO'
            )
            total_pedido = Decimal('0.00')

            for _, item in carrito.items():
                variante = VarianteCalzado.objects.select_for_update().get(id=item['variante_id'])
                cant = int(item['cantidad'])
                if variante.stock < cant:
                    raise ValueError(f"Sin stock suficiente para {variante}.")

                variante.stock -= cant
                variante.save()

                precio_unit = variante.calzado.precio_final
                DetallePedido.objects.create(
                    pedido=pedido,
                    variante=variante,
                    cantidad=cant,
                    precio_unitario=precio_unit
                )
                total_pedido += precio_unit * cant

            pedido.total = total_pedido
            pedido.save()
            request.session['carrito'] = {}
            messages.success(request, f"¡Pedido realizado con éxito! Código: {pedido.codigo}")
            return redirect('mis_pedidos')
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('ver_carrito')

@login_required
def mis_pedidos(request):
    pedidos = Pedido.objects.filter(cliente=request.user).order_by('-fecha').prefetch_related('detalles__variante__calzado')
    return render(request, 'tienda/mis_pedidos.html', {'pedidos': pedidos})

@login_required
def panel_admin(request):
    if not es_admin(request.user) and not request.user.is_superuser:
        messages.error(request, "Acceso restringido a Administradores.")
        return redirect('catalogo')

    calzados = Calzado.objects.all().prefetch_related('variantes', 'promociones').order_by('-creado_en')
    pedidos = Pedido.objects.filter(estado='CONFIRMADO').order_by('-fecha')
    ingresos_totales = sum(p.total for p in pedidos)

    form_calzado = CalzadoForm()
    form_promo = PromocionForm()

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'crear_calzado':
            form_calzado = CalzadoForm(request.POST, request.FILES)
            if form_calzado.is_valid():
                form_calzado.save()
                messages.success(request, "Nuevo calzado registrado.")
                return redirect('panel_admin')
        elif accion == 'crear_promo':
            form_promo = PromocionForm(request.POST)
            if form_promo.is_valid():
                form_promo.save()
                messages.success(request, "Promoción creada correctamente.")
                return redirect('panel_admin')

    return render(request, 'tienda/panel_admin.html', {
        'calzados': calzados,
        'pedidos': pedidos,
        'ingresos_totales': ingresos_totales,
        'form_calzado': form_calzado,
        'form_promo': form_promo,
    })

@login_required
def editar_calzado(request, calzado_id):
    if not es_admin(request.user) and not request.user.is_superuser:
        return redirect('catalogo')

    calzado = get_object_or_404(Calzado, id=calzado_id)
    form = CalzadoForm(request.POST or None, request.FILES or None, instance=calzado)
    form_variante = VarianteForm()

    if request.method == 'POST':
        if 'guardar_calzado' in request.POST and form.is_valid():
            form.save()
            messages.success(request, "Calzado actualizado correctamente.")
            return redirect('editar_calzado', calzado_id=calzado.id)
        elif 'agregar_variante' in request.POST:
            form_variante = VarianteForm(request.POST)
            if form_variante.is_valid():
                v = form_variante.save(commit=False)
                v.calzado = calzado
                v.save()
                messages.success(request, "Variante guardada.")
                return redirect('editar_calzado', calzado_id=calzado.id)

    return render(request, 'tienda/editar_calzado.html', {
        'calzado': calzado,
        'form': form,
        'form_variante': form_variante,
        'variantes': calzado.variantes.all(),
    })
