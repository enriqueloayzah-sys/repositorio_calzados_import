from django.urls import path
from . import views

urlpatterns = [
    path('', views.catalogo_view, name='catalogo'),
    path('registro/', views.registro_view, name='registro'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/agregar/<int:variante_id>/', views.agregar_carrito, name='agregar_carrito'),
    path('pedido/confirmar/', views.confirmar_pedido, name='confirmar_pedido'),
    path('mis-pedidos/', views.mis_pedidos, name='mis_pedidos'),
    path('administracion/', views.panel_admin, name='panel_admin'),
    path('administracion/calzado/<int:calzado_id>/', views.editar_calzado, name='editar_calzado'),
]
