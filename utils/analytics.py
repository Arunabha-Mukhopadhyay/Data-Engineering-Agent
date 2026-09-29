from utils.database import DatabaseUtil, database_config_from_env


REPORT_QUERIES = {
    "daily_ride_volume": """
        SELECT requested_at::date AS ride_date,
               COUNT(*) AS total_rides,
               COUNT(*) FILTER (WHERE status = 'completed') AS completed_rides
        FROM public.rides
        GROUP BY requested_at::date
        ORDER BY ride_date DESC
        LIMIT 30
    """,
    "cancellation_rate": """
        SELECT COUNT(*) AS total_rides,
               COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_rides,
               ROUND(
                   100.0 * COUNT(*) FILTER (WHERE status = 'cancelled')
                   / NULLIF(COUNT(*), 0),
                   2
               ) AS cancellation_percent
        FROM public.rides
    """,
    "monthly_payment_revenue": """
        SELECT DATE_TRUNC('month', payment_time)::date AS month,
               SUM(amount) AS completed_payment_revenue
        FROM public.payments
        WHERE payment_status = 'completed'
        GROUP BY DATE_TRUNC('month', payment_time)
        ORDER BY month DESC
        LIMIT 24
    """,
    "top_rated_drivers": """
        SELECT r.driver_id,
               u.first_name,
               u.last_name,
               ROUND(AVG(r.rating)::numeric, 2) AS average_rating,
               COUNT(*) AS rating_count
        FROM public.ratings AS r
        JOIN public.users AS u ON u.user_id = r.driver_id
        GROUP BY r.driver_id, u.first_name, u.last_name
        ORDER BY average_rating DESC, rating_count DESC
        LIMIT 10
    """,
}


def run_reports(db_config=None):
    config = db_config or database_config_from_env()
    return {
        name: DatabaseUtil(config).execute_sql(query)
        for name, query in REPORT_QUERIES.items()
    }


def main():
    for name, result in run_reports().items():
        print(f"\n{name.replace('_', ' ').title()}")
        print(result)


if __name__ == "__main__":
    main()