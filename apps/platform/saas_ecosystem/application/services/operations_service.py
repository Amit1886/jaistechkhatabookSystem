from apps.platform.saas_ecosystem.models import DeliveryAssignment, ForecastModel, RoutePlan, SalesmanTracking, VanSalesSession


class EnterpriseOperationsService:
    def create_route(self, tenant, **data):
        return RoutePlan.objects.create(tenant=tenant, **data)

    def track_salesman(self, tenant, salesman, latitude, longitude, **extra):
        return SalesmanTracking.objects.create(
            tenant=tenant,
            salesman=salesman,
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=extra.get("accuracy_meters", 0),
            route=extra.get("route"),
        )

    def start_van_sales(self, tenant, salesman, route=None, vehicle_no="", opening_stock=None):
        return VanSalesSession.objects.create(
            tenant=tenant,
            salesman=salesman,
            route=route,
            vehicle_no=vehicle_no,
            opening_stock=opening_stock or [],
        )

    def assign_delivery(self, tenant, reference_type, reference_id, delivery_user=None, route=None):
        return DeliveryAssignment.objects.create(
            tenant=tenant,
            reference_type=reference_type,
            reference_id=reference_id,
            delivery_user=delivery_user,
            route=route,
        )

    def run_forecast(self, forecast: ForecastModel):
        forecast.result = {"status": "ready", "horizon_days": forecast.horizon_days, "suggestions": []}
        forecast.save(update_fields=["result", "updated_at"])
        return forecast

