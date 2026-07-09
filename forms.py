"""Formularios WTForms (validación de servidor + protección CSRF)."""
import re

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, TextAreaField, SelectField, IntegerField,
    BooleanField, HiddenField,
)
from wtforms.validators import (
    DataRequired, Length, Email, EqualTo, ValidationError, Optional, NumberRange,
)

from models import SEVERITIES, EVENT_STATES, INCIDENT_STATES, ALERT_CHANNELS

PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


class RegisterForm(FlaskForm):
    name = StringField("Nombre completo", validators=[DataRequired(), Length(2, 120)])
    company = StringField("Empresa", validators=[DataRequired(), Length(2, 120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=160)])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(min=8, max=128)])
    confirm = PasswordField(
        "Confirmar contraseña",
        validators=[DataRequired(), EqualTo("password", message="Las contraseñas no coinciden.")],
    )

    def validate_password(self, field):
        if not PASSWORD_RE.match(field.data):
            raise ValidationError("Mínimo 8 caracteres, con al menos una letra y un número.")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Contraseña", validators=[DataRequired()])
    remember = BooleanField("Recordarme")


class IncidentForm(FlaskForm):
    title = StringField("Título", validators=[DataRequired(), Length(3, 200)])
    description = TextAreaField("Descripción", validators=[Optional(), Length(max=4000)])
    severity = SelectField(
        "Severidad",
        choices=[("critico", "Crítico"), ("aviso", "Aviso"), ("info", "Info")],
        validators=[DataRequired()],
    )
    assignee_id = SelectField("Asignar a", coerce=int, validators=[Optional()])
    event_id = HiddenField()

    def validate_severity(self, field):
        if field.data not in SEVERITIES:
            raise ValidationError("Severidad inválida.")


class IncidentUpdateForm(FlaskForm):
    """Cambio de estado / asignación desde el detalle del incidente."""
    status = SelectField(
        "Estado",
        choices=[
            ("abierto", "Abierto"),
            ("en_progreso", "En progreso"),
            ("escalado", "Escalado"),
            ("cerrado", "Cerrado"),
        ],
    )
    assignee_id = SelectField("Asignado a", coerce=int, validators=[Optional()])
    note = StringField("Nota (opcional)", validators=[Optional(), Length(max=400)])

    def validate_status(self, field):
        if field.data not in INCIDENT_STATES:
            raise ValidationError("Estado inválido.")


class EventStatusForm(FlaskForm):
    """Cambio de estado de un evento."""
    status = SelectField(
        "Estado",
        choices=[("nuevo", "Nuevo"), ("revisado", "Revisado"), ("resuelto", "Resuelto")],
    )

    def validate_status(self, field):
        if field.data not in EVENT_STATES:
            raise ValidationError("Estado inválido.")


class AlertRuleForm(FlaskForm):
    name = StringField("Nombre de la regla", validators=[DataRequired(), Length(3, 160)])
    target_severity = SelectField(
        "Severidad a vigilar",
        choices=[("critico", "Crítico"), ("aviso", "Aviso"), ("info", "Info")],
    )
    threshold = IntegerField(
        "Umbral (N.º de eventos)",
        validators=[DataRequired(message="Ingresá un número entero."),
                    NumberRange(min=1, max=100000, message="Debe ser un entero positivo.")],
    )
    window_minutes = IntegerField(
        "Ventana (minutos)",
        validators=[DataRequired(message="Ingresá un número entero."),
                    NumberRange(min=1, max=1440, message="Debe ser un entero positivo (máx. 1440).")],
    )
    channel = SelectField(
        "Canal de notificación",
        choices=[("in_app", "En la app"), ("email", "Email"), ("webhook", "Webhook"), ("sms", "SMS")],
    )
    active = BooleanField("Activa", default=True)

    def validate_target_severity(self, field):
        if field.data not in SEVERITIES:
            raise ValidationError("Severidad inválida.")

    def validate_channel(self, field):
        if field.data not in ALERT_CHANNELS:
            raise ValidationError("Canal inválido.")
