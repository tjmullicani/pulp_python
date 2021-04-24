from gettext import gettext as _
import logging
import os
import tempfile

from packaging.utils import canonicalize_name
from django.core.files import File
from django.template import Context, Template

from pulpcore.plugin import models

from pulp_python.app import models as python_models


log = logging.getLogger(__name__)

simple_index_template = """<!DOCTYPE html>
<html>
  <head>
    <title>Simple Index</title>
    <meta name="api-version" value="2" />
  </head>
  <body>
    {% for name, canonical_name in projects %}
    <a href="{{ canonical_name }}/">{{ name }}</a><br/>
    {% endfor %}
  </body>
</html>
"""


simple_detail_template = """<!DOCTYPE html>
<html>
<head>
  <title>Links for {{ project_name }}</title>
  <meta name="api-version" value="2" />
</head>
<body>
    <h1>Links for {{ project_name }}</h1>
    {% for name, path, sha256 in project_packages %}
    <a href="{{ path }}#sha256={{ sha256 }}" rel="internal">{{ name }}</a><br/>
    {% endfor %}
</body>
</html>
"""


def publish(repository_version_pk):
    """
    Create a Publication based on a RepositoryVersion.

    Args:
        repository_version_pk (str): Create a Publication from this RepositoryVersion.

    """
    repository_version = models.RepositoryVersion.objects.get(pk=repository_version_pk)

    log.info(_('Publishing: repository={repo}, version={version}').format(
        repo=repository_version.repository.name,
        version=repository_version.number,
    ))

    with tempfile.TemporaryDirectory("."):
        with python_models.PythonPublication.create(repository_version, True) as publication:
            write_simple_api(publication)

    log.info(_('Publication: {pk} created').format(pk=publication.pk))


def write_simple_api(publication):
    """
    Write metadata for the simple API.

    Writes metadata mimicking the simple api of PyPI for all python packages
    in the repository version.

    https://wiki.python.org/moin/PyPISimple

    Args:
        publication (pulpcore.plugin.models.Publication): A publication to generate metadata for

    """
    simple_dir = 'simple/'
    os.mkdir(simple_dir)
    project_names = (
        python_models.PythonPackageContent.objects.filter(
            pk__in=publication.repository_version.content
        )
        .order_by('name')
        .values_list('name', flat=True)
        .distinct()
    )

    index_names = [(name, canonicalize_name(name)) for name in project_names]

    # write the root index, which lists all of the projects for which there is a package available
    index_path = '{simple_dir}index.html'.format(simple_dir=simple_dir)
    with open(index_path, 'w') as index:
        context = Context({'projects': index_names})
        template = Template(simple_index_template)
        index.write(template.render(context))

    index_metadata = models.PublishedMetadata.create_from_file(
        relative_path=index_path,
        publication=publication,
        file=File(open(index_path, 'rb'))
    )
    index_metadata.save()

    if len(index_names) == 0:
        return

    releases = (
        python_models.PythonPackageContent.objects.filter(
            pk__in=publication.repository_version.content
        )
        .values("name", "filename", "contentartifact", "_artifacts__sha256")
        .order_by("name")
    )
    release_content_artifacts = (
        python_models.PythonPackageContent.objects.filter(
            pk__in=publication.repository_version.content
        )
        .values_list("contentartifact", flat=True)
    )
    remote_artifacts = (
        models.RemoteArtifact.objects.filter(
            content_artifact__in=release_content_artifacts
        )
        .values_list("content_artifact", "sha256").iterator()
    )
    # This can grow to 4 million elements if fully PyPI synced
    checksums = {ca: sha for ca, sha in remote_artifacts}

    def write_project_page():
        name = index_names[ind][1]
        project_dir = f'{simple_dir}{name}/'
        os.mkdir(project_dir)
        metadata_relative_path = f'{project_dir}index.html'

        with open(metadata_relative_path, 'w') as simple_metadata:
            context = Context({
                'project_name': name,
                'project_packages': package_releases
            })
            template = Template(simple_detail_template)
            simple_metadata.write(template.render(context))

        project_metadata = models.PublishedMetadata.create_from_file(
            relative_path=metadata_relative_path,
            publication=publication,
            file=File(open(metadata_relative_path, 'rb'))
        )
        project_metadata.save()  # change to bulk create when multi-table supported

    ind = 0
    current_name = index_names[ind][0]
    package_releases = []
    for release in releases.iterator():
        if release['name'] != current_name:
            write_project_page()
            package_releases = []
            ind += 1
            current_name = index_names[ind][0]
        content_artifact = release['contentartifact']
        relative_path = release['filename']
        path = f"../../{release['filename']}"
        checksum = release['_artifacts__sha256'] or checksums[content_artifact]
        package_releases.append((relative_path, path, checksum))
    write_project_page()  # Write the final project's page
