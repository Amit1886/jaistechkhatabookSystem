import React, { useEffect, useState } from "react";
import { Card, DataTable, KPIWidget, WorkflowBadge } from "../components";
import { workforceApi } from "../../services/workforceApi";

export function EcosystemOperationsCloud() {
  const [data, setData] = useState(null);
  const [gigs, setGigs] = useState([]);
  const [partners, setPartners] = useState([]);
  const [marketplace, setMarketplace] = useState([]);

  useEffect(() => {
    Promise.all([
      workforceApi.ecosystemCommandCenter(),
      workforceApi.gigTasks(),
      workforceApi.partners(),
      workforceApi.marketplaceListings(),
    ])
      .then(([summary, gigRows, partnerRows, listingRows]) => {
        setData(summary);
        setGigs(gigRows.results || gigRows);
        setPartners(partnerRows.results || partnerRows);
        setMarketplace(listingRows.results || listingRows);
      })
      .catch(() => setData(null));
  }, []);

  return (
    <div className="workforce-dashboard ecosystem-operations-cloud">
      <KPIWidget label="Open Gigs" value={data?.open_gigs ?? "-"} />
      <KPIWidget label="Remote Live" value={data?.remote_sessions ?? "-"} tone="green" />
      <KPIWidget label="Partners" value={data?.partners ?? "-"} tone="violet" />
      <KPIWidget label="Wallet Liability" value={data?.wallet_liability ?? "-"} tone="amber" />

      <Card title="Gig Economy Queue" className="wide-card">
        <DataTable rows={gigs.slice(0, 8)} columns={["title", "gig_type", "status", "payout_amount", "assignment_score"]} />
      </Card>

      <Card title="Partner Cloud">
        <div className="feed-list">
          {partners.slice(0, 6).map((partner) => (
            <p key={partner.id}>
              <strong>{partner.name}</strong>
              <span>{partner.partner_type}</span>
            </p>
          ))}
        </div>
      </Card>

      <Card title="Marketplace Pipeline">
        <div className="feed-list">
          {marketplace.slice(0, 6).map((listing) => (
            <p key={listing.id}>
              <WorkflowBadge state={listing.status === "open" ? "review" : "completed"} />
              <strong>{listing.title}</strong>
              <span>{listing.listing_type}</span>
            </p>
          ))}
        </div>
      </Card>

      <Card title="Training Cloud">
        <div className="feed-list">
          {(data?.certifications || []).map((row) => (
            <p key={row.status}>
              <strong>{row.status}</strong>
              <span>{row.total} certifications</span>
            </p>
          ))}
        </div>
      </Card>
    </div>
  );
}
