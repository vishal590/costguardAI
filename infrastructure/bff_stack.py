"""
CDK Stack for CostGuard Auth + BFF (Backend-for-Frontend).

- Cognito User Pool for login (username/password).
- BFF Lambda: validates JWT, proxies requests to CostGuard APIs with API keys (keys never sent to frontend).
- API Gateway for BFF (proxy all paths to Lambda).

Deploy with context or env for API URLs and keys, e.g.:
  cdk deploy CostGuardBFFStack -c bff_main_url=https://xxx/prod -c bff_main_key=xxx ...
"""
import os
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_cognito as cognito,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_logs as logs,
    CfnOutput,
)
from constructs import Construct


class BFFStack(Stack):
    """
    Auth (Cognito) + BFF Lambda and API Gateway.
    Frontend uses BFF URL and sends Bearer token; BFF adds API keys and forwards to backends.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------------------
        # Cognito User Pool
        # ---------------------------------------------------------------------
        user_pool = cognito.UserPool(
            self, "CostGuardUserPool",
            user_pool_name="costguard-users",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(username=True, email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )
        user_pool_client = user_pool.add_client(
            "CostGuardWebClient",
            user_pool_client_name="costguard-web",
            auth_flows=cognito.AuthFlow(user_password=True, user_srp=True),
            generate_secret=False,
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
        )

        # ---------------------------------------------------------------------
        # BFF Lambda
        # ---------------------------------------------------------------------
        repo_root = os.path.join(os.path.dirname(__file__), "..")
        user_access_table = dynamodb.Table(self, "UserAccessTable", table_name="costguard-user-access",
            partition_key=dynamodb.Attribute(name="subject", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST, removal_policy=RemovalPolicy.RETAIN)
        bff_env = {
            "BFF_ACCESS_GRANTS_TABLE": user_access_table.table_name,
            "BFF_ACCESS_GRANTS": self.node.try_get_context("bff_access_grants") or os.environ.get("BFF_ACCESS_GRANTS", "{}"),
            "BFF_ACCOUNT_ID": Stack.of(self).account,
            "BFF_USER_POOL_ID": user_pool.user_pool_id,
            "BFF_USER_POOL_CLIENT_ID": user_pool_client.user_pool_client_id,
            "BFF_MAIN_BASE_URL": self.node.try_get_context("bff_main_url") or os.environ.get("BFF_MAIN_BASE_URL", ""),
            "BFF_MAIN_API_KEY": self.node.try_get_context("bff_main_key") or os.environ.get("BFF_MAIN_API_KEY", ""),
            "BFF_MULTI_ACCOUNT_BASE_URL": self.node.try_get_context("bff_multi_account_url") or os.environ.get("BFF_MULTI_ACCOUNT_BASE_URL", ""),
            "BFF_MULTI_ACCOUNT_API_KEY": self.node.try_get_context("bff_multi_account_key") or os.environ.get("BFF_MULTI_ACCOUNT_API_KEY", ""),
            "BFF_AIML_BASE_URL": self.node.try_get_context("bff_aiml_url") or os.environ.get("BFF_AIML_BASE_URL", ""),
            "BFF_AIML_API_KEY": self.node.try_get_context("bff_aiml_key") or os.environ.get("BFF_AIML_API_KEY", ""),
            "BFF_AUTONOMOUS_BASE_URL": self.node.try_get_context("bff_autonomous_url") or os.environ.get("BFF_AUTONOMOUS_BASE_URL", ""),
            "BFF_AUTONOMOUS_API_KEY": self.node.try_get_context("bff_autonomous_key") or os.environ.get("BFF_AUTONOMOUS_API_KEY", ""),
        }
        bff_lambda = lambda_.Function(
            self, "BFFLambda",
            function_name="CostGuard-BFF",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="src.bff_handler.handler",
            code=lambda_.Code.from_asset(
                repo_root,
                exclude=[
                    # Local runtime bundles, credentials and generated output are not Lambda code.
                    ".artifacts", ".artifacts/**", ".aws", ".aws/**",
                    ".env", ".env.*", ".codex", ".agents", "htmlcov",
                    "*.key", "*.pem", "*.whl", "*.zip", "*.tar.gz", "*.tgz", "cdk.context.json",
                    "**/__pycache__", "**/*.pyc", "node_modules",
                    "cdk.out", "infrastructure/cdk.out", "infrastructure/*", ".git", ".github",
                    "tests", "docs", "scripts", "*.md", ".venv", "venv", "__pycache__", "*.pyc",
                    "*.txt", ".hypothesis", ".kiro", ".ruff_cache", ".pytest_cache", "*.log",
                ],
            ),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment=bff_env,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )
        bff_lambda.add_to_role_policy(iam.PolicyStatement(actions=["dynamodb:GetItem"], resources=[user_access_table.table_arn]))
        bff_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["cognito-idp:GetUser"],
            resources=[user_pool.user_pool_arn],
        ))

        # ---------------------------------------------------------------------
        # API Gateway (proxy all to BFF)
        # ---------------------------------------------------------------------
        bff_api = apigateway.RestApi(
            self, "BFFAPI",
            rest_api_name="CostGuard-BFF",
            description="BFF: auth + proxy to CostGuard APIs",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )
        bff_integration = apigateway.LambdaIntegration(bff_lambda, proxy=True)
        proxy_resource = bff_api.root.add_resource("{proxy+}")
        proxy_resource.add_method("ANY", bff_integration)
        bff_api.root.add_method("ANY", bff_integration)

        # ---------------------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------------------
        CfnOutput(self, "UserAccessTableName", value=user_access_table.table_name)
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id, description="Cognito User Pool ID (set VITE_COGNITO_USER_POOL_ID)")
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id, description="Cognito App Client ID (set VITE_COGNITO_CLIENT_ID)")
        CfnOutput(self, "BFFApiUrl", value=bff_api.url, description="BFF API base URL (set VITE_BFF_BASE_URL in frontend)")
        CfnOutput(self, "CognitoRegion", value=Stack.of(self).region, description="Cognito region (set VITE_AWS_REGION for Cognito)")
