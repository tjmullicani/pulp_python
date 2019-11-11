# Generated by Django 2.2.7 on 2019-11-11 23:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_repository_pulp_type'),
        ('python', '0003_jsonfield'),
    ]

    operations = [
        migrations.CreateModel(
            name='PythonRepository',
            fields=[
                ('repository_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, related_name='python_pythonrepository', serialize=False, to='core.Repository')),
            ],
            options={
                'default_related_name': '%(app_label)s_%(model_name)s',
            },
            bases=('core.repository',),
        ),
    ]
