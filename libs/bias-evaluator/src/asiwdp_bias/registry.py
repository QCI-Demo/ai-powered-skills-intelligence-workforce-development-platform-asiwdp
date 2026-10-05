"""MLflow model registry integration."""

from __future__ import annotations

import logging
from typing import Optional

import mlflow
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from asiwdp_bias.config import BiasConfig
from asiwdp_bias.models import ModelEndpoint

logger = logging.getLogger(__name__)


class MLflowModelRegistry:
    """Interface to MLflow Model Registry for fetching model endpoints."""

    def __init__(self, config: BiasConfig):
        """Initialize with configuration.
        
        Args:
            config: BiasConfig with MLflow connection settings
        """
        self.config = config
        self._client: Optional[MlflowClient] = None

    @property
    def client(self) -> MlflowClient:
        """Lazy-initialized MLflow client."""
        if self._client is None:
            mlflow.set_tracking_uri(self.config.mlflow_tracking_uri)
            if self.config.mlflow_registry_uri:
                mlflow.set_registry_uri(self.config.mlflow_registry_uri)
            self._client = MlflowClient()
        return self._client

    def list_registered_models(self) -> list[str]:
        """List all registered model names.
        
        Returns:
            List of model names in the registry
        """
        try:
            models = self.client.search_registered_models()
            return [m.name for m in models]
        except MlflowException as e:
            logger.error(f"Failed to list registered models: {e}")
            raise

    def get_model_versions(
        self,
        model_name: str,
        stages: Optional[list[str]] = None,
    ) -> list[ModelEndpoint]:
        """Get all versions of a model, optionally filtered by stage.
        
        Args:
            model_name: Name of the registered model
            stages: Optional list of stages to filter (e.g., ["Production", "Staging"])
            
        Returns:
            List of ModelEndpoint objects for matching versions
        """
        try:
            if stages:
                # Filter by specific stages
                endpoints = []
                for stage in stages:
                    versions = self.client.get_latest_versions(model_name, stages=[stage])
                    for v in versions:
                        endpoints.append(self._version_to_endpoint(v))
                return endpoints
            else:
                # Get all versions
                filter_string = f"name='{model_name}'"
                versions = self.client.search_model_versions(filter_string)
                return [self._version_to_endpoint(v) for v in versions]
        except MlflowException as e:
            logger.error(f"Failed to get versions for model {model_name}: {e}")
            raise

    def get_production_models(self) -> list[ModelEndpoint]:
        """Get all models currently in Production stage.
        
        Returns:
            List of ModelEndpoint objects for production models
        """
        return self.get_models_by_stage("Production")

    def get_staging_models(self) -> list[ModelEndpoint]:
        """Get all models currently in Staging stage.
        
        Returns:
            List of ModelEndpoint objects for staging models
        """
        return self.get_models_by_stage("Staging")

    def get_models_by_stage(self, stage: str) -> list[ModelEndpoint]:
        """Get all models at a specific stage.
        
        Args:
            stage: Model stage (None, Staging, Production, Archived)
            
        Returns:
            List of ModelEndpoint objects
        """
        endpoints = []
        try:
            model_names = self.list_registered_models()
            for name in model_names:
                versions = self.get_model_versions(name, stages=[stage])
                endpoints.extend(versions)
        except MlflowException as e:
            logger.error(f"Failed to get models for stage {stage}: {e}")
            raise
        return endpoints

    def get_latest_version(
        self,
        model_name: str,
        stage: Optional[str] = None,
    ) -> Optional[ModelEndpoint]:
        """Get the latest version of a model.
        
        Args:
            model_name: Name of the registered model
            stage: Optional stage filter
            
        Returns:
            ModelEndpoint for latest version, or None if not found
        """
        try:
            stages = [stage] if stage else None
            versions = self.client.get_latest_versions(model_name, stages=stages)
            if versions:
                # Return the most recent by version number
                latest = max(versions, key=lambda v: int(v.version))
                return self._version_to_endpoint(latest)
            return None
        except MlflowException as e:
            logger.error(f"Failed to get latest version for {model_name}: {e}")
            raise

    def load_model(self, endpoint: ModelEndpoint):
        """Load model from MLflow for inference.
        
        Args:
            endpoint: ModelEndpoint with model location
            
        Returns:
            Loaded model object (type depends on model flavor)
        """
        try:
            return mlflow.pyfunc.load_model(endpoint.model_uri)
        except MlflowException as e:
            logger.error(f"Failed to load model {endpoint.model_uri}: {e}")
            raise

    def _version_to_endpoint(self, version) -> ModelEndpoint:
        """Convert MLflow ModelVersion to ModelEndpoint."""
        tags = dict(version.tags) if version.tags else {}
        return ModelEndpoint(
            name=version.name,
            version=str(version.version),
            stage=version.current_stage,
            run_id=version.run_id,
            source=version.source,
            description=version.description,
            tags=tags,
        )
