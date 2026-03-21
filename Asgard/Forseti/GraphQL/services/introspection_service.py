"""
GraphQL Introspection Service.

Introspects GraphQL endpoints to extract schema information.
"""

import json
from typing import Any, Optional, cast
from urllib.request import Request, urlopen
from urllib.error import URLError

from Asgard.Forseti.GraphQL.models.graphql_models import (
    GraphQLConfig,
    GraphQLSchema,
)
from Asgard.Forseti.GraphQL.services._introspection_helpers import (
    parse_introspection_result,
    schema_to_sdl,
)


class IntrospectionService:
    """
    Service for introspecting GraphQL endpoints.

    Queries GraphQL endpoints to extract schema information.

    Usage:
        service = IntrospectionService()
        schema = service.introspect("http://localhost:4000/graphql")
        print(f"Types: {len(schema.types)}")
    """

    INTROSPECTION_QUERY = """
    query IntrospectionQuery {
      __schema {
        queryType { name }
        mutationType { name }
        subscriptionType { name }
        types {
          ...FullType
        }
        directives {
          name
          description
          locations
          args {
            ...InputValue
          }
        }
      }
    }

    fragment FullType on __Type {
      kind
      name
      description
      fields(includeDeprecated: true) {
        name
        description
        args {
          ...InputValue
        }
        type {
          ...TypeRef
        }
        isDeprecated
        deprecationReason
      }
      inputFields {
        ...InputValue
      }
      interfaces {
        ...TypeRef
      }
      enumValues(includeDeprecated: true) {
        name
        description
        isDeprecated
        deprecationReason
      }
      possibleTypes {
        ...TypeRef
      }
    }

    fragment InputValue on __InputValue {
      name
      description
      type {
        ...TypeRef
      }
      defaultValue
    }

    fragment TypeRef on __Type {
      kind
      name
      ofType {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
                ofType {
                  kind
                  name
                  ofType {
                    kind
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
    """

    def __init__(self, config: Optional[GraphQLConfig] = None):
        """
        Initialize the introspection service.

        Args:
            config: Optional configuration for introspection behavior.
        """
        self.config = config or GraphQLConfig()

    def introspect(
        self,
        endpoint: str,
        headers: Optional[dict[str, str]] = None,
        timeout: int = 30
    ) -> GraphQLSchema:
        """
        Introspect a GraphQL endpoint.

        Args:
            endpoint: GraphQL endpoint URL.
            headers: Optional HTTP headers.
            timeout: Request timeout in seconds.

        Returns:
            Introspected GraphQLSchema.

        Raises:
            ConnectionError: If the endpoint cannot be reached.
            ValueError: If the response is not valid GraphQL.
        """
        if not self.config.allow_introspection:
            raise ValueError("Introspection is disabled in configuration")

        result = self._execute_query(endpoint, headers, timeout)
        return parse_introspection_result(result)

    def _execute_query(
        self,
        endpoint: str,
        headers: Optional[dict[str, str]],
        timeout: int
    ) -> dict[str, Any]:
        """Execute the introspection query."""
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        payload = json.dumps({
            "query": self.INTROSPECTION_QUERY,
        }).encode("utf-8")

        request = Request(endpoint, data=payload, headers=request_headers)

        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except URLError as e:
            raise ConnectionError(f"Failed to connect to endpoint: {e}")

        if "errors" in result:
            errors = result["errors"]
            error_messages = [e.get("message", str(e)) for e in errors]
            raise ValueError(f"GraphQL errors: {', '.join(error_messages)}")

        if "data" not in result or "__schema" not in result["data"]:
            raise ValueError("Invalid introspection response")

        return cast(dict[str, Any], result["data"]["__schema"])

    def to_sdl(self, schema: GraphQLSchema) -> str:
        """
        Convert an introspected schema to SDL.

        Args:
            schema: Introspected schema.

        Returns:
            SDL string representation.
        """
        return schema_to_sdl(schema)
