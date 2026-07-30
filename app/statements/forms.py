"""Statement upload form."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import SelectField, SubmitField
from wtforms.validators import DataRequired


class UploadStatementForm(FlaskForm):
    account_id = SelectField(
        "Import into account",
        validators=[DataRequired(message="Please pick an account.")],
    )
    statement = FileField(
        "Statement file (CSV)",
        validators=[
            FileRequired(message="Please select a file to upload."),
            FileAllowed(["csv"], message="Only .csv files are supported for now."),
        ],
    )
    submit = SubmitField("Upload & parse")
