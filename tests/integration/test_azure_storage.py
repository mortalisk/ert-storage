import os
import pytest


@pytest.fixture
def azure_client():
    """
    A synchronous Azure Blob Storage ContainerClient
    """
    from ert_storage.database import HAS_AZURE_BLOB_STORAGE, ENV_BLOB, BLOB_CONTAINER

    if not HAS_AZURE_BLOB_STORAGE:
        pytest.skip("An Azure Storage connection is required to run these tests")

    import asyncio
    from ert_storage.database import create_container_if_not_exist
    from azure.storage.blob import ContainerClient

    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_container_if_not_exist())

    yield ContainerClient.from_connection_string(os.environ[ENV_BLOB], BLOB_CONTAINER)


def test_blob(client, azure_client, simple_ensemble):
    ensemble_id = simple_ensemble()

    # List all blobs prior to adding file
    pre_blobs = {blob.name for blob in azure_client.list_blobs()}

    # Standard file upload and download
    client.post(
        f"/ensembles/{ensemble_id}/records/foo/file",
        files={"file": ("somefile", open("/bin/bash", "rb"), "foo/bar")},
    )
    resp = client.get(f"/ensembles/{ensemble_id}/records/foo")
    assert resp.status_code == 200

    # List all blobs after adding file
    post_blobs = {blob.name for blob in azure_client.list_blobs()}

    diff_blobs = list(post_blobs - pre_blobs)
    assert len(diff_blobs) == 1

    blob = azure_client.get_blob_client(diff_blobs[0])
    assert blob.download_blob().readall() == resp.content


def test_blocked_blob(client, azure_client, simple_ensemble):

    ensemble_id = simple_ensemble()

    size = 12 * 1024**2
    block_size = 4 * 1024**2

    def _generate_blob_chunks():
        data = []
        with open("/dev/urandom", "rb") as file_handle:
            for _ in range(size // block_size):
                data.append(file_handle.read(block_size))
        return data

    client.post(
        f"/ensembles/{ensemble_id}/records/foo/blob",
    )
    chunks = _generate_blob_chunks()
    for i, chunk in enumerate(chunks):
        client.put(
            f"/ensembles/{ensemble_id}/records/foo/blob",
            params={"block_index": i},
            data=chunk,
        )

    client.patch(
        f"/ensembles/{ensemble_id}/records/foo/blob",
    )

    resp = client.get(
        f"/ensembles/{ensemble_id}/records/foo",
    )

    assert b"".join(chunks) == resp.content
