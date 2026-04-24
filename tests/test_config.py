from app.config import Settings


def test_placeholder_values_are_normalized_to_none() -> None:
    settings = Settings(
        gemini_api_key="__set_if_using_gemini__",
        openai_compatible_api_key="__optional_for_local_servers__",
        qdrant_api_key="__set_only_for_remote_qdrant__",
        mlflow_tracking_uri="__optional_http_or_file_uri__",
    )

    assert settings.gemini_api_key is None
    assert settings.openai_compatible_api_key is None
    assert settings.qdrant_api_key is None
    assert settings.mlflow_tracking_uri is None
