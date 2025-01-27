from dataclasses import dataclass
from typing import Callable, Dict, List, Type

import pytest
from typing_extensions import Annotated

from litestar import Controller, Litestar, post
from litestar._openapi.datastructures import OpenAPIContext
from litestar._openapi.request_body import create_request_body
from litestar.datastructures.upload_file import UploadFile
from litestar.enums import RequestEncodingType
from litestar.handlers import BaseRouteHandler
from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.spec import Example, RequestBody
from litestar.params import Body
from litestar.typing import FieldDefinition


@dataclass
class FormData:
    cv: UploadFile
    image: UploadFile


RequestBodyFactory = Callable[[BaseRouteHandler, FieldDefinition], RequestBody]


@pytest.fixture()
def openapi_context() -> OpenAPIContext:
    return OpenAPIContext(
        openapi_config=OpenAPIConfig(title="test", version="1.0.0", create_examples=True),
        plugins=[],
    )


@pytest.fixture()
def create_request(openapi_context: OpenAPIContext) -> RequestBodyFactory:
    def _factory(route_handler: BaseRouteHandler, data_field: FieldDefinition) -> RequestBody:
        return create_request_body(
            context=openapi_context,
            handler_id=route_handler.handler_id,
            resolved_data_dto=route_handler.resolve_data_dto(),
            data_field=data_field,
        )

    return _factory


def test_create_request_body(person_controller: Type[Controller], create_request: RequestBodyFactory) -> None:
    for route in Litestar(route_handlers=[person_controller]).routes:
        for route_handler, _ in route.route_handler_map.values():  # type: ignore[union-attr]
            handler_fields = route_handler.parsed_fn_signature.parameters
            if "data" in handler_fields:
                request_body = create_request(route_handler, handler_fields["data"])
                assert request_body


def test_upload_single_file_schema_generation() -> None:
    @post(path="/file-upload")
    async def handle_file_upload(
        data: UploadFile = Body(media_type=RequestEncodingType.MULTI_PART),
    ) -> None:
        return None

    app = Litestar([handle_file_upload])
    schema = app.openapi_schema.to_schema()

    assert schema["paths"]["/file-upload"]["post"]["requestBody"]["content"]["multipart/form-data"]["schema"] == {
        "properties": {"file": {"type": "string", "format": "binary", "contentMediaType": "application/octet-stream"}},
        "type": "object",
    }


def test_upload_list_of_files_schema_generation() -> None:
    @post(path="/file-list-upload")
    async def handle_file_list_upload(
        data: List[UploadFile] = Body(media_type=RequestEncodingType.MULTI_PART),
    ) -> None:
        return None

    app = Litestar([handle_file_list_upload])
    schema = app.openapi_schema.to_schema()

    assert schema["paths"]["/file-list-upload"]["post"]["requestBody"]["content"]["multipart/form-data"]["schema"] == {
        "type": "object",
        "properties": {
            "files": {
                "items": {"type": "string", "contentMediaType": "application/octet-stream", "format": "binary"},
                "type": "array",
            }
        },
    }


def test_upload_file_dict_schema_generation() -> None:
    @post(path="/file-dict-upload")
    async def handle_file_list_upload(
        data: Dict[str, UploadFile] = Body(media_type=RequestEncodingType.MULTI_PART),
    ) -> None:
        return None

    app = Litestar([handle_file_list_upload])
    schema = app.openapi_schema.to_schema()

    assert schema["paths"]["/file-dict-upload"]["post"]["requestBody"]["content"]["multipart/form-data"]["schema"] == {
        "type": "object",
        "properties": {
            "files": {
                "items": {"type": "string", "contentMediaType": "application/octet-stream", "format": "binary"},
                "type": "array",
            }
        },
    }


def test_upload_file_model_schema_generation() -> None:
    @post(path="/form-upload")
    async def handle_form_upload(
        data: FormData = Body(media_type=RequestEncodingType.MULTI_PART),
    ) -> None:
        return None

    app = Litestar([handle_form_upload])
    schema = app.openapi_schema.to_schema()

    assert schema["paths"]["/form-upload"]["post"]["requestBody"]["content"]["multipart/form-data"] == {
        "schema": {"$ref": "#/components/schemas/FormData"}
    }
    assert schema["components"] == {
        "schemas": {
            "FormData": {
                "properties": {
                    "cv": {"type": "string", "contentMediaType": "application/octet-stream", "format": "binary"},
                    "image": {"type": "string", "contentMediaType": "application/octet-stream", "format": "binary"},
                },
                "type": "object",
                "required": ["cv", "image"],
                "title": "FormData",
            }
        }
    }


def test_example_in_request_body_schema_generation() -> None:
    @dataclass
    class SampleClass:
        name: str
        age: int

    @post(path="/example")
    async def handler(
        data: Annotated[SampleClass, Body(examples=[Example(summary="example", value={"name": "John", "age": 30})])],
    ) -> None:
        return None

    app = Litestar([handler])
    schema = app.openapi_schema.to_schema()

    assert schema["paths"]["/example"]["post"]["requestBody"]["content"]["application/json"]["examples"] == {
        "data-example-1": {"summary": "example", "value": {"name": "John", "age": 30}}
    }
