import type { ServiceLogin } from "../../api/types";
import { Badge, statusTone } from "../../components/Badge";

export function ServicesMatrix({ services }: { services: ServiceLogin[] }) {
  return (
    <div className="service-grid">
      {services.map((service) => (
        <div className="service-card" key={service.service}>
          <strong>{service.service}</strong>
          <Badge tone={statusTone(service.status)}>{service.status}</Badge>
          <small>{service.message || service.last_success_at || "No activity"}</small>
        </div>
      ))}
    </div>
  );
}
