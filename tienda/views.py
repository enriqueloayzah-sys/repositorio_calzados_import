import uuid
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from .models import (
    PerfilUsuario, Categoria, Calzado, VarianteCalzado,
    Promocion, Pedido, DetallePedido
)
from .forms import RegistroClienteForm, CalzadoForm, VarianteForm, PromocionForm


def es_admin(user):
    return user.is_authenticated and (
        user.is_superuser or (hasattr(user, 'perfil') and user.perfil.rol == 'ADMIN')
    )


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
        usuario_input = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
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
    categorias = Categoria.objects.all().order_by('nombre')
    calzados = Calzado.objects.filter(activo=True).prefetch_related('variantes', 'promociones').order_by('-creado_en')

    cat_id = request.GET.get('categoria', '').strip()
    solo_ofertas = request.GET.get('ofertas', '').strip()
    buscar = request.GET.get('q', '').strip()
    talla_filtro = request.GET.get('talla', '').strip()

    if cat_id:
        calzados = calzados.filter(categoria_id=cat_id)
    if buscar:
        calzados = calzados.filter(nombre__icontains=buscar) | calzados.filter(marca__icontains=buscar)
    if talla_filtro:
        calzados = calzados.filter(variantes__talla__iexact=talla_filtro, variantes__stock__gt=0).distinct()

    ahora = timezone.now()
    promociones_vigentes = Promocion.objects.filter(
        activa=True,
        fecha_inicio__lte=ahora,
        fecha_fin__gte=ahora,
        calzado__activo=True
    ).select_related('calzado', 'calzado__categoria').order_by('-porcentaje_descuento')

    items = []
    for c in calzados:
        promo = c.promocion_vigente()
        if solo_ofertas and not promo:
            continue
        variantes_disp = c.variantes.filter(stock__gt=0)
        if talla_filtro:
            variantes_disp = variantes_disp.filter(talla__iexact=talla_filtro)
        items.append({
            'obj': c,
            'promo': promo,
            'precio_final': c.precio_final,
            'variantes_disponibles': variantes_disp,
        })

    carrito = request.session.get('carrito', {})
    total_items_carrito = sum(item['cantidad'] for item in carrito.values())

    return render(request, 'tienda/catalogo.html', {
        'items': items,
        'categorias': categorias,
        'promociones_vigentes': promociones_vigentes,
        'total_items_carrito': total_items_carrito,
        'solo_ofertas': bool(solo_ofertas),
        'buscar': buscar,
        'talla_filtro': talla_filtro,
        'cat_seleccionada': cat_id,
    })


@login_required
def agregar_carrito(request, variante_id):
    if request.method == 'POST':
        variante = get_object_or_404(VarianteCalzado, id=variante_id)
        try:
            cantidad = int(request.POST.get('cantidad', 1))
        except (ValueError, TypeError):
            cantidad = 1

        if cantidad < 1 or cantidad > variante.stock:
            messages.error(request, "Cantidad no válida o stock insuficiente.")
            return redirect('catalogo')

        carrito = request.session.get('carrito', {})
        key = str(variante.id)
        actual = carrito.get(key, {'cantidad': 0})['cantidad']
        if actual + cantidad > variante.stock:
            messages.error(request, "La cantidad supera el stock disponible para esa talla y color.")
            return redirect('catalogo')

        carrito[key] = {
            'variante_id': variante.id,
            'calzado_nombre': f"{variante.calzado.marca} {variante.calzado.nombre}",
            'talla': variante.talla,
            'color': variante.color,
            'precio': str(variante.calzado.precio_final),
            'stock_max': variante.stock,
            'cantidad': actual + cantidad,
        }
        request.session['carrito'] = carrito
        messages.success(request, "Producto agregado al carrito.")
    return redirect('ver_carrito')


@login_required
def actualizar_carrito(request, variante_id):
    if request.method == 'POST':
        carrito = request.session.get('carrito', {})
        key = str(variante_id)
        if key in carrito:
            try:
                nueva_cant = int(request.POST.get('cantidad', 1))
            except (ValueError, TypeError):
                nueva_cant = 1

            variante = get_object_or_404(VarianteCalzado, id=variante_id)
            if nueva_cant <= 0:
                del carrito[key]
                messages.info(request, "Producto eliminado del carrito.")
            elif nueva_cant > variante.stock:
                messages.error(request, f"Solo hay {variante.stock} pares disponibles de esta variante.")
            else:
                carrito[key]['cantidad'] = nueva_cant
                carrito[key]['precio'] = str(variante.calzado.precio_final)
                carrito[key]['stock_max'] = variante.stock
                messages.success(request, "Cantidad actualizada.")
            request.session['carrito'] = carrito
    return redirect('ver_carrito')


@login_required
def eliminar_carrito(request, variante_id):
    if request.method == 'POST':
        carrito = request.session.get('carrito', {})
        key = str(variante_id)
        if key in carrito:
            del carrito[key]
            request.session['carrito'] = carrito
            messages.info(request, "Producto quitado del carrito.")
    return redirect('ver_carrito')


@login_required
def ver_carrito(request):
    carrito = request.session.get('carrito', {})
    filas = []
    total = Decimal('0.00')
    for _, item in carrito.items():
        variante = VarianteCalzado.objects.filter(id=item['variante_id']).first()
        precio_actual = variante.calzado.precio_final if variante else Decimal(item['precio'])
        stock_max = variante.stock if variante else item['cantidad']
        subtotal = (precio_actual * item['cantidad']).quantize(Decimal('0.01'))
        total += subtotal
        filas.append({
            **item,
            'precio': precio_actual,
            'stock_max': stock_max,
            'subtotal': subtotal
        })
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
            codigo_entrega = f"CI-{uuid.uuid4().hex[:8].upper()}"
            pedido = Pedido.objects.create(
                cliente=request.user,
                codigo=codigo_entrega,
                total=Decimal('0.00'),
                estado='CONFIRMADO',
                estado_entrega='PENDIENTE'
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

            pedido.total = total_pedido.quantize(Decimal('0.01'))
            pedido.save()
            request.session['carrito'] = {}
            messages.success(
                request,
                f"¡Pedido confirmado! Tu código de entrega es: {pedido.codigo}. Preséntalo al recoger o coordinar tu calzado."
            )
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
    if not es_admin(request.user):
        messages.error(request, "Acceso restringido a Administradores.")
        return redirect('catalogo')

    calzados = Calzado.objects.all().prefetch_related('variantes', 'promociones').order_by('-creado_en')
    buscar_codigo = request.GET.get('codigo_entrega', '').strip().upper()
    filtro_entrega = request.GET.get('estado_entrega', '').strip()

    pedidos = Pedido.objects.filter(estado='CONFIRMADO').order_by('-fecha').prefetch_related('detalles__variante__calzado', 'cliente')
    if buscar_codigo:
        pedidos = pedidos.filter(codigo__icontains=buscar_codigo)
    if filtro_entrega in ('PENDIENTE', 'ENTREGADO'):
        pedidos = pedidos.filter(estado_entrega=filtro_entrega)

    todos_confirmados = Pedido.objects.filter(estado='CONFIRMADO')
    ingresos_totales = sum((p.total for p in todos_confirmados), Decimal('0.00'))
    pendientes_entrega_count = todos_confirmados.filter(estado_entrega='PENDIENTE').count()

    form_calzado = CalzadoForm()
    form_promo = PromocionForm()

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'crear_calzado':
            form_calzado = CalzadoForm(request.POST, request.FILES)
            if form_calzado.is_valid():
                nuevo = form_calzado.save()
                messages.success(request, f"Calzado '{nuevo.nombre}' registrado. Ahora agrega sus tallas y stock.")
                return redirect('editar_calzado', calzado_id=nuevo.id)
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
        'pendientes_entrega_count': pendientes_entrega_count,
        'buscar_codigo': buscar_codigo,
        'filtro_entrega': filtro_entrega,
        'form_calzado': form_calzado,
        'form_promo': form_promo,
    })


@login_required
def marcar_entregado(request, pedido_id):
    if not es_admin(request.user):
        messages.error(request, "Acceso restringido a Administradores.")
        return redirect('catalogo')

    if request.method == 'POST':
        pedido = get_object_or_404(Pedido, id=pedido_id)
        if pedido.estado_entrega != 'ENTREGADO':
            pedido.estado_entrega = 'ENTREGADO'
            pedido.fecha_entrega = timezone.now()
            pedido.entregado_por = request.user
            pedido.save()
            messages.success(request, f"Pedido {pedido.codigo} marcado como ENTREGADO.")
        else:
            messages.info(request, f"El pedido {pedido.codigo} ya figuraba como entregado.")
    return redirect('panel_admin')


@login_required
def editar_calzado(request, calzado_id):
    if not es_admin(request.user):
        messages.error(request, "Acceso restringido a Administradores.")
        return redirect('catalogo')

    calzado = get_object_or_404(Calzado, id=calzado_id)
    form = CalzadoForm(request.POST or None, request.FILES or None, instance=calzado)
    form_variante = VarianteForm()

    if request.method == 'POST':
        if 'guardar_calzado' in request.POST and form.is_valid():
            form.save()
            messages.success(request, "Datos del calzado actualizados.")
            return redirect('editar_calzado', calzado_id=calzado.id)
        elif 'agregar_variante' in request.POST:
            form_variante = VarianteForm(request.POST)
            if form_variante.is_valid():
                talla = form_variante.cleaned_data['talla'].strip()
                color = form_variante.cleaned_data['color'].strip()
                stock = form_variante.cleaned_data['stock']
                existente = VarianteCalzado.objects.filter(
                    calzado=calzado, talla__iexact=talla, color__iexact=color
                ).first()
                if existente:
                    existente.stock = stock
                    existente.save()
                    messages.success(request, f"Stock actualizado para Talla {existente.talla} ({existente.color}): {existente.stock} pares.")
                else:
                    VarianteCalzado.objects.create(
                        calzado=calzado, talla=talla, color=color, stock=stock
                    )
                    messages.success(request, f"Variante Talla {talla} ({color}) agregada con {stock} pares.")
                return redirect('editar_calzado', calzado_id=calzado.id)

    return render(request, 'tienda/editar_calzado.html', {
        'calzado': calzado,
        'form': form,
        'form_variante': form_variante,
        'variantes': calzado.variantes.all().order_by('talla', 'color'),
    })


@login_required
def editar_variante(request, variante_id):
    if not es_admin(request.user):
        messages.error(request, "Acceso restringido a Administradores.")
        return redirect('catalogo')

    variante = get_object_or_404(VarianteCalzado, id=variante_id)
    if request.method == 'POST':
        talla = request.POST.get('talla', '').strip()
        color = request.POST.get('color', '').strip()
        try:
            stock = int(request.POST.get('stock', 0))
        except (ValueError, TypeError):
            stock = 0

        if not talla or not color or stock < 0:
            messages.error(request, "Ingresa talla, color y un stock válido (0 o mayor).")
            return redirect('editar_calzado', calzado_id=variante.calzado.id)

        duplicada = VarianteCalzado.objects.filter(
            calzado=variante.calzado,
            talla__iexact=talla,
            color__iexact=color
        ).exclude(id=variante.id).first()

        if duplicada:
            messages.error(request, f"Ya existe otra variante con talla {talla} y color {color}.")
            return redirect('editar_calzado', calzado_id=variante.calzado.id)

        variante.talla = talla
        variante.color = color
        variante.stock = stock
        variante.save()
        messages.success(request, f"Variante actualizada: Talla {variante.talla} ({variante.color}) - {variante.stock} pares.")

    return redirect('editar_calzado', calzado_id=variante.calzado.id)


@login_required
def eliminar_variante(request, variante_id):
    if not es_admin(request.user):
        messages.error(request, "Acceso restringido a Administradores.")
        return redirect('catalogo')

    variante = get_object_or_404(VarianteCalzado, id=variante_id)
    calzado_id = variante.calzado.id
    if request.method == 'POST':
        try:
            variante.delete()
            messages.success(request, "Talla/variante eliminada correctamente.")
        except Exception:
            messages.error(request, "No se puede eliminar esta variante porque ya tiene pedidos asociados.")

    return redirect('editar_calzado', calzado_id=calzado_id)
