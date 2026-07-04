from fastapi import Response, status

from app.core.exceptions import AppError
from app.core.validations.messages import Msg


def assert_validation_response(response: Response, expected_errors: dict):
    """
    Reusable helper to verify standard 422 validation responses.
    """
    data = response.json()

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    assert data["message"] == AppError.VALIDATION_ERROR.message

    # Assert Specific Field Errors
    for field, expected_msgs in expected_errors.items():
        # Check if the field exists in the error response
        assert field in data["errors"], (
            f"Expected error for '{field}', but got: {list(data['errors'].keys())}"
        )

        actual_msgs = data["errors"][field]

        if field == "email":
            for msg in actual_msgs:
                assert Msg.EMAIL_INVALID in msg, (
                    f"Expected '{Msg.EMAIL_INVALID}' in {actual_msgs} for field '{field}'"
                )
        else:
            for msg in expected_msgs:
                assert msg in actual_msgs, (
                    f"Expected '{msg}' in {actual_msgs} for field '{field}'"
                )
