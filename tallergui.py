"""
Sistema de Gestión Mecánica App de escritorio - Interfaz gráfica (PyQt6)
------------------------------------------------------
Camila Cabrera Barajas - 18/10/2026
"""

import json
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QComboBox, QDialog,
    QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QSpinBox,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

# ======================================================================
#  CAPA DE BASE DE DATOS  (aquí vive todo lo relacionado con consultas)
# ======================================================================
class Db:
    """Envuelve tu clase de conexión. Lanza RuntimeError si la consulta falla."""

    def __init__(self, conexion, motor):
        self.cnx = conexion
        self.motor = motor  # "postgres" o "sqlserver"

    def _correr(self, sql, params=None):
        # Escribimos los parámetros con "?"; PostgreSQL (psycopg2) usa "%s"
        if self.motor == "postgres":
            sql = sql.replace("?", "%s")
        res = json.loads(self.cnx.ejecutar_consulta(sql, params))
        if not res.get("estado"):
            raise RuntimeError(res.get("mensaje", "Error en la consulta"))
        return res

    def filas(self, sql, params=None):
        """SELECT -> lista de diccionarios."""
        return self._correr(sql, params).get("registros") or []

    def ejecutar(self, sql, params=None):
        """INSERT / UPDATE / DELETE."""
        self._correr(sql, params)

    def escalar(self, sql, params=None):
        """SELECT que devuelve un solo valor (COUNT, SUM...)."""
        filas = self.filas(sql, params)
        if not filas:
            return 0
        val = list(filas[0].values())[0]
        return 0 if val is None else val


# ======================================================================
#  CONFIGURACIÓN DE CATÁLOGOS
#  Para agregar una tabla nueva solo agregas otro bloque aquí.
#  campos: (columna, etiqueta, tipo, obligatorio, extra)
#     tipos: txt | int | money | fk
# ======================================================================
CATALOGOS = {
    "Clientes": {
        "icono": "👤",
        "tabla": "Cliente",
        "pk": "id_cliente",
        "select": "SELECT id_cliente, nombre, telefono, correo, direccion FROM Cliente",
        "orden": "id_cliente",
        "buscar": ["nombre", "telefono", "correo"],
        "columnas": [("id_cliente", "ID", "int"), ("nombre", "Nombre", "txt"),
                     ("telefono", "Teléfono", "txt"), ("correo", "Correo", "txt"),
                     ("direccion", "Dirección", "txt")],
        "campos": [("nombre", "Nombre", "txt", True, None),
                   ("telefono", "Teléfono", "txt", False, None),
                   ("correo", "Correo", "txt", False, None),
                   ("direccion", "Dirección", "txt", False, None)],
    },
    "Vehículos": {
        "icono": "🚗",
        "tabla": "Vehiculo",
        "pk": "id_vehiculo",
        "select": ("SELECT v.id_vehiculo, c.nombre AS cliente, v.marca, v.modelo, v.anio, "
                   "v.placas, v.kilometraje FROM Vehiculo v "
                   "INNER JOIN Cliente c ON v.id_cliente = c.id_cliente"),
        "orden": "v.id_vehiculo",
        "buscar": ["c.nombre", "v.marca", "v.modelo", "v.placas"],
        "columnas": [("id_vehiculo", "ID", "int"), ("cliente", "Dueño", "txt"),
                     ("marca", "Marca", "txt"), ("modelo", "Modelo", "txt"),
                     ("anio", "Año", "txt"), ("placas", "Placas", "txt"),
                     ("kilometraje", "Km", "int")],
        "campos": [("id_cliente", "Cliente", "fk", True, ("Cliente", "id_cliente", "nombre")),
                   ("marca", "Marca", "txt", True, None),
                   ("modelo", "Modelo", "txt", True, None),
                   ("anio", "Año", "int", False, (1950, 2100)),
                   ("placas", "Placas", "txt", False, None),
                   ("kilometraje", "Kilometraje", "int", False, (0, 5_000_000))],
    },
    "Mecánicos": {
        "icono": "🔧",
        "tabla": "Mecanico",
        "pk": "id_mecanico",
        "select": "SELECT id_mecanico, nombre, especialidad, telefono FROM Mecanico",
        "orden": "id_mecanico",
        "buscar": ["nombre", "especialidad", "telefono"],
        "columnas": [("id_mecanico", "ID", "int"), ("nombre", "Nombre", "txt"),
                     ("especialidad", "Especialidad", "txt"), ("telefono", "Teléfono", "txt")],
        "campos": [("nombre", "Nombre", "txt", True, None),
                   ("especialidad", "Especialidad", "txt", False, None),
                   ("telefono", "Teléfono", "txt", False, None)],
    },
    "Administradores": {
        "icono": "🔐",
        "tabla": "Administrador",
        "pk": "id_administrador",
        "select": "SELECT id_administrador, nombre, usuario FROM Administrador",
        "orden": "id_administrador",
        "buscar": ["nombre", "usuario"],
        "columnas": [("id_administrador", "ID", "int"), ("nombre", "Nombre", "txt"),
                     ("usuario", "Usuario", "txt")],
        "campos": [("nombre", "Nombre", "txt", True, None),
                   ("usuario", "Usuario", "txt", True, None),
                   ("contrasena", "Contraseña", "pass", True, None)],
    },
    "Refacciones": {
        "icono": "⚙️",
        "tabla": "Refaccion",
        "pk": "id_refaccion",
        "select": "SELECT id_refaccion, nombre, precio_unitario, cantidad_stock FROM Refaccion",
        "orden": "id_refaccion",
        "buscar": ["nombre"],
        "columnas": [("id_refaccion", "ID", "int"), ("nombre", "Refacción", "txt"),
                     ("precio_unitario", "Precio unit.", "money"),
                     ("cantidad_stock", "Stock", "stock")],
        "campos": [("nombre", "Nombre", "txt", True, None),
                   ("precio_unitario", "Precio unitario", "money", True, (0, 10_000_000)),
                   ("cantidad_stock", "Stock", "int", True, (0, 1_000_000))],
    },
}

# Consultas de solo lectura (módulo Operaciones)
OPERACIONES = {
    "Órdenes de servicio": {
        "icono": "📋",
        "sql": ("SELECT o.id_orden, c.nombre AS cliente, v.marca, v.modelo, m.nombre AS mecanico, "
                "o.fecha_inicio, o.fecha_fin, o.estado FROM OrdenServicio o "
                "INNER JOIN Vehiculo v ON o.id_vehiculo = v.id_vehiculo "
                "INNER JOIN Cliente c ON v.id_cliente = c.id_cliente "
                "INNER JOIN Mecanico m ON o.id_mecanico = m.id_mecanico "
                "ORDER BY o.id_orden DESC"),
        "columnas": [("id_orden", "Orden", "int"), ("cliente", "Cliente", "txt"),
                     ("marca", "Marca", "txt"), ("modelo", "Modelo", "txt"),
                     ("mecanico", "Mecánico", "txt"), ("fecha_inicio", "Inicio", "txt"),
                     ("fecha_fin", "Fin", "txt"), ("estado", "Estado", "estado")],
    },
    "Citas": {
        "icono": "📅",
        "sql": ("SELECT ci.id_cita, ci.fecha, ci.hora, c.nombre AS cliente, v.marca, v.modelo, "
                "ci.motivo FROM Cita ci INNER JOIN Cliente c ON ci.id_cliente = c.id_cliente "
                "INNER JOIN Vehiculo v ON ci.id_vehiculo = v.id_vehiculo ORDER BY ci.fecha, ci.hora"),
        "columnas": [("id_cita", "Cita", "int"), ("fecha", "Fecha", "txt"), ("hora", "Hora", "hora"),
                     ("cliente", "Cliente", "txt"), ("marca", "Marca", "txt"),
                     ("modelo", "Modelo", "txt"), ("motivo", "Motivo", "txt")],
    },
    "Pagos": {
        "icono": "💰",
        "sql": "SELECT id_pago, id_orden, fecha, monto, metodo_pago FROM Pago ORDER BY fecha DESC",
        "columnas": [("id_pago", "Pago", "int"), ("id_orden", "Orden", "int"),
                     ("fecha", "Fecha", "txt"), ("monto", "Monto", "money"),
                     ("metodo_pago", "Método", "txt")],
    },
}


# ======================================================================
#  ESTILO
# ======================================================================
QSS = """
* { font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; color: #e5e7eb; }
QMainWindow, QDialog, #contenido { background: #0b1020; }
#sidebar { background: #0f172a; border-right: 1px solid #1e293b; }
#logo { font-size: 20px; font-weight: 800; color: #22d3ee; padding: 18px 12px 2px 18px; }
#sublogo { font-size: 10px; color: #64748b; padding: 0 12px 14px 18px; letter-spacing: 2px; }
#seccion { color: #475569; font-size: 10px; font-weight: 700; padding: 14px 18px 4px 18px; letter-spacing: 2px; }
QPushButton#nav { background: transparent; border: none; text-align: left; padding: 11px 18px;
                  border-radius: 10px; margin: 1px 10px; color: #94a3b8; font-size: 14px; }
QPushButton#nav:hover { background: #1e293b; color: white; }
QPushButton#nav:checked { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0891b2, stop:1 #6366f1);
                          color: white; font-weight: 600; }
QPushButton#sub { background: transparent; border: none; text-align: left; padding: 8px 18px 8px 38px;
                  border-radius: 8px; margin: 0 10px; color: #94a3b8; }
QPushButton#sub:hover { background: #1e293b; color: white; }
QPushButton#sub:checked { background: #1e293b; color: #22d3ee; font-weight: 600; }
QPushButton#salir { background: transparent; border: none; text-align: left; padding: 11px 18px;
                    margin: 1px 10px; color: #f87171; border-radius: 10px; font-size: 14px; }
QPushButton#salir:hover { background: #3f1d1d; }
#titulo { font-size: 26px; font-weight: 800; color: white; }
#subtitulo { color: #64748b; }
#card { background: #111a30; border: 1px solid #1e293b; border-radius: 16px; }
#cardnum { font-size: 30px; font-weight: 800; color: #22d3ee; }
#cardlbl { color: #94a3b8; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #111a30; border: 1px solid #1e293b;
        border-radius: 10px; padding: 8px 12px; selection-background-color: #6366f1; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 1px solid #22d3ee; }
QComboBox QAbstractItemView { background: #111a30; selection-background-color: #6366f1; }
QPushButton.accion { border: none; border-radius: 10px; padding: 9px 18px; font-weight: 600; color: white; }
QPushButton[rol="nuevo"] { background: #10b981; } QPushButton[rol="nuevo"]:hover { background: #059669; }
QPushButton[rol="editar"] { background: #6366f1; } QPushButton[rol="editar"]:hover { background: #4f46e5; }
QPushButton[rol="borrar"] { background: #ef4444; } QPushButton[rol="borrar"]:hover { background: #dc2626; }
QPushButton[rol="neutro"] { background: #1e293b; } QPushButton[rol="neutro"]:hover { background: #334155; }
QPushButton[rol] { border: none; border-radius: 10px; padding: 9px 18px; font-weight: 600; color: white; }
QTableWidget { background: #0f172a; border: 1px solid #1e293b; border-radius: 12px;
               gridline-color: #1e293b; alternate-background-color: #111a30; }
QTableWidget::item { padding: 6px; }
QTableWidget::item:selected { background: #312e81; color: white; }
QHeaderView::section { background: #1e293b; color: #22d3ee; padding: 9px; border: none; font-weight: 700; }
QScrollBar:vertical { background: #0f172a; width: 10px; }
QScrollBar::handle:vertical { background: #334155; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QMessageBox { background: #0f172a; }
"""


def formatear(valor, tipo):
    if valor is None:
        return ""
    if tipo == "money":
        try:
            return f"${float(valor):,.2f}"
        except (TypeError, ValueError):
            return str(valor)
    if tipo == "hora":
        return str(valor)[:5]
    return str(valor)


def llenar_tabla(tabla, registros, columnas):
    """Pinta una lista de diccionarios en un QTableWidget."""
    tabla.setRowCount(0)
    tabla.setColumnCount(len(columnas))
    tabla.setHorizontalHeaderLabels([c[1] for c in columnas])
    for r in registros:
        fila = tabla.rowCount()
        tabla.insertRow(fila)
        for j, (clave, _, tipo) in enumerate(columnas):
            texto = formatear(r.get(clave), tipo)
            item = QTableWidgetItem(texto)
            if tipo in ("int", "money", "stock"):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if tipo == "stock" and texto.isdigit():
                item.setForeground(QColor("#f87171" if int(texto) <= 10 else "#34d399"))
            if tipo == "estado":
                t = texto.lower()
                if "proceso" in t or "pendiente" in t:
                    item.setForeground(QColor("#fbbf24"))
                elif "termin" in t or "autoriz" in t:
                    item.setForeground(QColor("#34d399"))
            if tipo == "money":
                item.setForeground(QColor("#34d399"))
            tabla.setItem(fila, j, item)


def crear_tabla():
    t = QTableWidget()
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setShowGrid(False)
    return t


def boton(texto, rol):
    b = QPushButton(texto)
    b.setProperty("rol", rol)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def encabezado(titulo, subtitulo):
    caja = QVBoxLayout()
    t = QLabel(titulo); t.setObjectName("titulo")
    s = QLabel(subtitulo); s.setObjectName("subtitulo")
    caja.addWidget(t); caja.addWidget(s)
    return caja


# ======================================================================
#  FORMULARIO (Insertar / Actualizar)
# ======================================================================
class FormDialog(QDialog):
    def __init__(self, db, cfg, datos=None, parent=None):
        super().__init__(parent)
        self.db, self.cfg = db, cfg
        self.setWindowTitle(("Editar " if datos else "Nuevo ") + cfg["tabla"])
        self.setMinimumWidth(420)
        self.widgets = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 20)
        titulo = QLabel(("✏️  Editar registro" if datos else "➕  Nuevo registro"))
        titulo.setObjectName("titulo"); titulo.setStyleSheet("font-size:20px;")
        lay.addWidget(titulo)

        form = QFormLayout()
        form.setSpacing(12)
        for col, etiqueta, tipo, _, extra in cfg["campos"]:
            if tipo == "int":
                w = QSpinBox(); w.setRange(*(extra or (0, 2_000_000_000)))
            elif tipo == "money":
                w = QDoubleSpinBox(); w.setRange(*(extra or (0, 10_000_000))); w.setDecimals(2)
                w.setPrefix("$ ")
            elif tipo == "fk":
                w = QComboBox()
                tabla_fk, pk_fk, texto_fk = extra
                for r in db.filas(f"SELECT {pk_fk}, {texto_fk} FROM {tabla_fk} ORDER BY {texto_fk}"):
                    w.addItem(str(r[texto_fk]), int(r[pk_fk]))
            elif tipo == "pass":
                w = QLineEdit(); w.setEchoMode(QLineEdit.EchoMode.Password)
            else:
                w = QLineEdit()
            self.widgets[col] = w
            form.addRow(etiqueta + ("  *" if cfg_obligatorio(cfg, col) else ""), w)
        lay.addLayout(form)

        if datos:
            self._rellenar(datos)

        fila = QHBoxLayout(); fila.addStretch()
        cancelar = boton("Cancelar", "neutro"); cancelar.clicked.connect(self.reject)
        guardar = boton("💾  Guardar", "nuevo"); guardar.clicked.connect(self._validar)
        fila.addWidget(cancelar); fila.addWidget(guardar)
        lay.addSpacing(8); lay.addLayout(fila)

    def _rellenar(self, datos):
        for col, _, tipo, _, _ in self.cfg["campos"]:
            v, w = datos.get(col), self.widgets[col]
            if v is None:
                continue
            if tipo == "int":
                w.setValue(int(v))
            elif tipo == "money":
                w.setValue(float(v))
            elif tipo == "fk":
                w.setCurrentIndex(max(0, w.findData(int(v))))
            else:
                w.setText(str(v))

    def valores(self):
        """Devuelve los valores en el mismo orden que cfg['campos']."""
        out = []
        for col, _, tipo, _, _ in self.cfg["campos"]:
            w = self.widgets[col]
            if tipo == "int":
                out.append(w.value())
            elif tipo == "money":
                out.append(w.value())
            elif tipo == "fk":
                out.append(w.currentData())
            else:
                out.append(w.text().strip() or None)
        return out

    def _validar(self):
        for (col, etiqueta, tipo, obligatorio, _), val in zip(self.cfg["campos"], self.valores()):
            if obligatorio and val in (None, ""):
                QMessageBox.warning(self, "Campo obligatorio", f"El campo «{etiqueta}» es obligatorio.")
                return
        self.accept()


def cfg_obligatorio(cfg, col):
    return any(c[0] == col and c[3] for c in cfg["campos"])


# ======================================================================
#  PÁGINA CRUD  (Consultar, Insertar, Actualizar, Eliminar)
# ======================================================================
class CrudPage(QWidget):
    def __init__(self, db, nombre, cfg):
        super().__init__()
        self.db, self.nombre, self.cfg = db, nombre, cfg

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24); lay.setSpacing(16)
        lay.addLayout(encabezado(f"{cfg['icono']}  {nombre}", f"Catálogo de {nombre.lower()}: consultar, insertar, actualizar y eliminar"))

        barra = QHBoxLayout()
        self.buscador = QLineEdit(); self.buscador.setPlaceholderText("🔍  Buscar...")
        self.buscador.setMinimumWidth(280)
        self.buscador.textChanged.connect(self.cargar)
        b_nuevo = boton("➕  Insertar", "nuevo");    b_nuevo.clicked.connect(self.insertar)
        b_edit = boton("✏️  Actualizar", "editar"); b_edit.clicked.connect(self.actualizar)
        b_del = boton("🗑  Eliminar", "borrar");    b_del.clicked.connect(self.eliminar)
        b_ref = boton("⟳  Consultar", "neutro");    b_ref.clicked.connect(self.cargar)
        barra.addWidget(self.buscador); barra.addStretch()
        for b in (b_ref, b_nuevo, b_edit, b_del):
            barra.addWidget(b)
        lay.addLayout(barra)

        self.tabla = crear_tabla()
        self.tabla.doubleClicked.connect(self.actualizar)
        lay.addWidget(self.tabla)
        self.lbl_total = QLabel(""); self.lbl_total.setObjectName("subtitulo")
        lay.addWidget(self.lbl_total)

    # ---------------- CONSULTAR ----------------
    def cargar(self, *_):
        sql = self.cfg["select"]
        params = None
        texto = self.buscador.text().strip()
        if texto:
            filtros = " OR ".join(f"LOWER({c}) LIKE LOWER(?)" for c in self.cfg["buscar"])
            sql += f" WHERE {filtros}"
            params = tuple(f"%{texto}%" for _ in self.cfg["buscar"])
        sql += f" ORDER BY {self.cfg['orden']}"
        try:
            filas = self.db.filas(sql, params)
        except RuntimeError as e:
            QMessageBox.critical(self, "Error", str(e)); return
        llenar_tabla(self.tabla, filas, self.cfg["columnas"])
        self.lbl_total.setText(f"{len(filas)} registro(s)")

    def _id_seleccionado(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Selecciona un registro", "Primero selecciona una fila de la tabla.")
            return None
        return int(self.tabla.item(fila, 0).text())  # la columna 0 siempre es el ID

    # ---------------- INSERTAR ----------------
    def insertar(self):
        try:
            dlg = FormDialog(self.db, self.cfg, parent=self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            cols = [c[0] for c in self.cfg["campos"]]
            sql = (f"INSERT INTO {self.cfg['tabla']} ({', '.join(cols)}) "
                   f"VALUES ({', '.join('?' for _ in cols)})")
            self.db.ejecutar(sql, tuple(dlg.valores()))
            self.cargar()
        except RuntimeError as e:
            QMessageBox.critical(self, "No se pudo insertar", str(e))

    # ---------------- ACTUALIZAR ----------------
    def actualizar(self, *_):
        id_ = self._id_seleccionado()
        if id_ is None:
            return
        try:
            cols = [c[0] for c in self.cfg["campos"]]
            actual = self.db.filas(
                f"SELECT {', '.join(cols)} FROM {self.cfg['tabla']} WHERE {self.cfg['pk']} = ?", (id_,))
            if not actual:
                QMessageBox.warning(self, "No encontrado", "El registro ya no existe."); self.cargar(); return
            dlg = FormDialog(self.db, self.cfg, datos=actual[0], parent=self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            sets = ", ".join(f"{c} = ?" for c in cols)
            sql = f"UPDATE {self.cfg['tabla']} SET {sets} WHERE {self.cfg['pk']} = ?"
            self.db.ejecutar(sql, tuple(dlg.valores()) + (id_,))
            self.cargar()
        except RuntimeError as e:
            QMessageBox.critical(self, "No se pudo actualizar", str(e))

    # ---------------- ELIMINAR ----------------
    def eliminar(self):
        id_ = self._id_seleccionado()
        if id_ is None:
            return
        resp = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Eliminar definitivamente el registro #{id_}?\nEsta acción no se puede deshacer.")
        if resp != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.ejecutar(f"DELETE FROM {self.cfg['tabla']} WHERE {self.cfg['pk']} = ?", (id_,))
            self.cargar()
        except RuntimeError as e:
            QMessageBox.critical(
                self, "No se pudo eliminar",
                f"{e}\n\nProbablemente tiene registros relacionados (llave foránea).")


# ======================================================================
#  PÁGINA DE SOLO LECTURA
# ======================================================================
class ConsultaPage(QWidget):
    def __init__(self, db, nombre, cfg):
        super().__init__()
        self.db, self.cfg = db, cfg
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24); lay.setSpacing(16)
        fila = QHBoxLayout()
        fila.addLayout(encabezado(f"{cfg['icono']}  {nombre}", "Consulta de solo lectura"))
        fila.addStretch()
        b = boton("⟳  Actualizar", "neutro"); b.clicked.connect(self.cargar)
        fila.addWidget(b, alignment=Qt.AlignmentFlag.AlignTop)
        lay.addLayout(fila)
        self.tabla = crear_tabla()
        lay.addWidget(self.tabla)
        self.lbl_total = QLabel(""); self.lbl_total.setObjectName("subtitulo")
        lay.addWidget(self.lbl_total)

    def cargar(self):
        try:
            filas = self.db.filas(self.cfg["sql"])
        except RuntimeError as e:
            QMessageBox.critical(self, "Error", str(e)); return
        llenar_tabla(self.tabla, filas, self.cfg["columnas"])
        self.lbl_total.setText(f"{len(filas)} registro(s)")


# ======================================================================
#  INICIO (dashboard)
# ======================================================================
class InicioPage(QWidget):
    def __init__(self, db, motor_nombre):
        super().__init__()
        self.db = db
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24); lay.setSpacing(20)
        lay.addLayout(encabezado("👋  Bienvenido al Taller", f"Resumen operativo  ·  Base de datos activa: {motor_nombre}"))

        self.grid = QHBoxLayout(); self.grid.setSpacing(16)
        lay.addLayout(self.grid)
        lay.addStretch()
        self.cards = {}
        for clave, etiqueta in [("cli", "Clientes"), ("veh", "Vehículos"), ("proc", "Órdenes en proceso"),
                                ("stock", "Stock crítico (≤10)"), ("ing", "Ingresos cobrados")]:
            card = QFrame(); card.setObjectName("card")
            v = QVBoxLayout(card); v.setContentsMargins(20, 18, 20, 18)
            num = QLabel("-"); num.setObjectName("cardnum")
            lbl = QLabel(etiqueta); lbl.setObjectName("cardlbl")
            v.addWidget(num); v.addWidget(lbl)
            self.cards[clave] = num
            self.grid.addWidget(card)

    def cargar(self):
        try:
            d = self.db
            self.cards["cli"].setText(str(d.escalar("SELECT COUNT(*) FROM Cliente")))
            self.cards["veh"].setText(str(d.escalar("SELECT COUNT(*) FROM Vehiculo")))
            self.cards["proc"].setText(str(d.escalar("SELECT COUNT(*) FROM OrdenServicio WHERE estado = 'En proceso'")))
            self.cards["stock"].setText(str(d.escalar("SELECT COUNT(*) FROM Refaccion WHERE cantidad_stock <= 10")))
            self.cards["ing"].setText(formatear(d.escalar("SELECT SUM(monto) FROM Pago"), "money"))
        except RuntimeError as e:
            QMessageBox.critical(self, "Error", str(e))


# ======================================================================
#  VENTANA PRINCIPAL
# ======================================================================
class Ventana(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("Taller Mecánico · Sistema de Gestión")
        self.resize(1250, 780)

        raiz = QWidget(); self.setCentralWidget(raiz)
        h = QHBoxLayout(raiz); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)

        # ----- Sidebar -----
        side = QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(250)
        sl = QVBoxLayout(side); sl.setContentsMargins(0, 0, 0, 14); sl.setSpacing(0)
        logo = QLabel("🛠  TALLER PRO"); logo.setObjectName("logo")
        sub = QLabel("GESTIÓN MECÁNICA"); sub.setObjectName("sublogo")
        sl.addWidget(logo); sl.addWidget(sub)

        self.grupo = QButtonGroup(self); self.grupo.setExclusive(True)
        self.stack = QStackedWidget()
        self.paginas = {}

        def agregar_pagina(clave, pagina):
            self.paginas[clave] = pagina
            self.stack.addWidget(pagina)

        def nuevo_nav(texto, clave, objeto="nav"):
            b = QPushButton(texto); b.setObjectName(objeto); b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=clave: self.ir(k))
            self.grupo.addButton(b)
            return b

        # Inicio
        agregar_pagina("inicio", InicioPage(db, "PostgreSQL" if db.motor == "postgres" else "SQL Server"))
        b_inicio = nuevo_nav("🏠   Inicio", "inicio"); b_inicio.setChecked(True)
        sl.addWidget(b_inicio)

        # Catálogos (desplegable)
        self.b_cat = QPushButton("📚   Catálogos  ▾"); self.b_cat.setObjectName("nav")
        self.b_cat.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_cat.clicked.connect(self._toggle_catalogos)
        sl.addWidget(self.b_cat)
        self.caja_cat = QWidget(); cl = QVBoxLayout(self.caja_cat)
        cl.setContentsMargins(0, 0, 0, 6); cl.setSpacing(0)
        for nombre, cfg in CATALOGOS.items():
            agregar_pagina(nombre, CrudPage(db, nombre, cfg))
            cl.addWidget(nuevo_nav(f"{cfg['icono']}  {nombre}", nombre, "sub"))
        sl.addWidget(self.caja_cat)

        # Operaciones
        sec = QLabel("OPERACIONES"); sec.setObjectName("seccion"); sl.addWidget(sec)
        for nombre, cfg in OPERACIONES.items():
            agregar_pagina(nombre, ConsultaPage(db, nombre, cfg))
            sl.addWidget(nuevo_nav(f"{cfg['icono']}   {nombre}", nombre))

        sl.addStretch()
        b_salir = QPushButton("⏻   Salir"); b_salir.setObjectName("salir")
        b_salir.setCursor(Qt.CursorShape.PointingHandCursor)
        b_salir.clicked.connect(self.close)
        sl.addWidget(b_salir)

        # ----- Contenido -----
        cont = QWidget(); cont.setObjectName("contenido")
        cv = QVBoxLayout(cont); cv.setContentsMargins(0, 0, 0, 0); cv.addWidget(self.stack)

        h.addWidget(side); h.addWidget(cont, 1)
        self.ir("inicio")

    def _toggle_catalogos(self):
        visible = not self.caja_cat.isVisible()
        self.caja_cat.setVisible(visible)
        self.b_cat.setText("📚   Catálogos  " + ("▾" if visible else "▸"))

    def ir(self, clave):
        pagina = self.paginas[clave]
        self.stack.setCurrentWidget(pagina)
        pagina.cargar()

    def closeEvent(self, e):
        if QMessageBox.question(self, "Salir", "¿Deseas cerrar el sistema?") == QMessageBox.StandardButton.Yes:
            e.accept()
        else:
            e.ignore()


# ======================================================================
#  SELECCIÓN DE MOTOR + ARRANQUE
# ======================================================================
class MotorDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.motor = None
        self.setWindowTitle("Seleccionar motor de base de datos")
        self.setFixedWidth(420)
        lay = QVBoxLayout(self); lay.setContentsMargins(28, 28, 28, 28); lay.setSpacing(12)
        t = QLabel("🛠  TALLER PRO"); t.setObjectName("titulo"); t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s = QLabel("Elige el motor de base de datos"); s.setObjectName("subtitulo")
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t); lay.addWidget(s); lay.addSpacing(10)
        for texto, motor in [("🐘   PostgreSQL", "postgres"), ("🗄   SQL Server", "sqlserver")]:
            b = boton(texto, "editar"); b.setMinimumHeight(46)
            b.clicked.connect(lambda _=False, m=motor: self._elegir(m))
            lay.addWidget(b)
        c = boton("Cancelar", "neutro"); c.clicked.connect(self.reject); lay.addWidget(c)

    def _elegir(self, motor):
        self.motor = motor
        self.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    app.setFont(QFont("Segoe UI", 10))

    dlg = MotorDialog()
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    # Mismas clases de conexión que ya usabas en la versión de consola
    if dlg.motor == "postgres":
        from conexion_postgrestaller import ConexionPostgresTaller
        conexion = ConexionPostgresTaller()
    else:
        from conexion_sqlservertaller import ConexionSqlServerTaller
        conexion = ConexionSqlServerTaller()

    if conexion.crear_conexion() is None:
        QMessageBox.critical(None, "Conexión", "Error al conectar. Verifica las credenciales.")
        return

    ventana = Ventana(Db(conexion, dlg.motor))
    ventana.show()
    codigo = app.exec()
    conexion.cerrar_conexion()
    sys.exit(codigo)


if __name__ == "__main__":
    main()