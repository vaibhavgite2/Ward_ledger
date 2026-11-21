# Data dictionary

All files are UTF-8 CSV (or GeoJSON). Dates are `YYYY-MM-DD`, timestamps `YYYY-MM-DD HH:MM` in IST. Coordinates are WGS84 decimal degrees. **Everything is synthetic and all contractors are fictional.**

## complaints.csv
One row per complaint received by BMC.

| Column | Description |
|---|---|
| complaint_id | Unique id, `BMC25-000123` |
| received_at | When the complaint was logged |
| channel | `MyBMC App`, `1916 Helpline`, `MyBMC Web Portal`, `Ward Office Walk-in` |
| category_reported | Category the citizen picked. About 18% are wrong or vague |
| description | Free text. English, Hinglish, Marathi or Hindi. Helpline rows are operator notes |
| language | `en`, `hi-en` (Hinglish), `mr` (Marathi), `hi` (Hindi) |
| locality_text | Locality as typed. Sometimes shortened |
| ward_code | BMC ward. Blank for about 7% |
| lat, lon | GPS. Mostly only for app complaints. Blank otherwise |
| gps_accuracy_m | Reported GPS accuracy in metres |
| photo_url | Placeholder image URL (no real photos) |
| photo_description | What the photo would show. Use it as a stand-in for image understanding |
| complainant_id | Anonymised hash. Not a real person |
| upvotes | "Me too" count on the app |
| status | `Open`, `In Progress`, `Resolved`, `Closed - Duplicate`, `Forwarded to MMRDA/PWD`, `Rejected - ...`, `Forwarded to SWM dept` |
| resolved_at | When the linked work order completed, if any |

## social_posts.csv
| Column | Description |
|---|---|
| post_id | Unique id |
| posted_at | Timestamp |
| source | `X (Twitter)`, `WhatsApp society group`, `WhatsApp ALM group`, `Instagram comment` |
| author_handle | Anonymised handle |
| text | Post text with emoji, hashtags, mixed scripts. Includes sarcasm, forwards and thank-yous |
| has_media | Y/N |
| likes_or_forwards | Engagement count |

## wards.csv / wards.geojson
| Column | Description |
|---|---|
| ward_code | Real BMC ward code (A, B, C, D, E, F/S, F/N, G/S, G/N, H/E, H/W, K/E, K/W, P/S, P/N, R/S, R/C, R/N, L, M/E, M/W, N, S, T) |
| ward_name | Main areas covered |
| zone | Zone grouping |
| assistant_commissioner_office | Ward office name |
| centroid_lat, centroid_lon | Approximate centre |
| approx_area_km2 | Area of the approximate polygon |
| population_est | Rough population |
| low_lying_index | 0 to 1, how flood-prone the ward is |
| monsoon_repair_budget_inr_2025 | Ward's monsoon road repair budget for Jun to Sep 2025, in rupees. Sized against actual spend, so some wards over or underspend |
| engineering_crews | Repair crews available per day |
| localities | Semicolon separated list |

The GeoJSON polygons are a Voronoi approximation around ward centres, not official boundaries. Point-in-polygon on them is consistent with the `ward_code` columns in this dataset.

## localities.csv
Gazetteer for geocoding text: `locality`, `ward_code`, `lat`, `lon`, `aliases` (alternate spellings and Devanagari).

## roads.csv / roads.geojson
| Column | Description |
|---|---|
| road_id | `RD0001` |
| road_name | Real arterial name, segment geometry is synthetic |
| segment_no | Segment order along that road in the ward |
| ward_code | Ward of the segment midpoint |
| road_type | `Highway`, `Arterial`, `Main`, `Local` |
| surface | Asphalt, Concrete (CC), Paver blocks |
| lanes | Lane count |
| length_m | Segment length |
| start_lat, start_lon, end_lat, end_lon | Endpoints |
| last_resurfaced | Date |
| under_dlp | Y if still under the original contractor's Defect Liability Period. Repairs here should be done by that contractor at no cost to BMC |
| bus_route | Y if BEST buses use it |

## flood_hotspots.csv
`hotspot_id`, `name`, `ward_code`, `lat`, `lon`, `flood_threshold_mm_per_day` (rain at which it usually floods), `tide_sensitive` (Y/N), `avg_water_depth_cm`, `avg_recession_hours`, `pumping_station_nearby`, `years_flagged_last_5`.

## rainfall_daily.csv
`date`, `station` (Santacruz, Colaba), `rainfall_mm`, `imd_category` (No rain, Light, Moderate, Heavy, Very heavy, Extremely heavy), `imd_alert` (Green, Yellow, Orange, Red).

## tides.csv
Two rows per day: `date`, `high_tide_time`, `height_m`, `big_tide_flag` (Y if >= 4.5 m).

## traffic.csv
`road_id`, `peak_hour_vehicles`, `avg_peak_speed_kmph`, `congestion_index_0_10`, `bus_routes_count`, `two_wheeler_share_pct`.

## accidents.csv
`accident_id`, `occurred_at`, `ward_code`, `road_id`, `lat`, `lon`, `vehicle_type`, `severity` (Minor, Grievous, Fatal), `probable_cause` (includes Pothole, Waterlogged road, Uneven road / open chamber).

## facilities.csv
`facility_id`, `type` (Hospital, School), `name`, `ward_code`, `lat`, `lon`, `beds_or_students`, `emergency_services`, `ambulance_entry_road` (nearest `road_id`).

## work_orders.csv
| Column | Description |
|---|---|
| work_order_id | `WO25-00001` |
| linked_complaint_ids | Pipe-separated complaint ids BMC linked to this job. Blank means no complaint was linked |
| ward_code, road_id | Where |
| work_type | Issue category |
| repair_method | Cold mix patch, Hot mix patch, Mastic asphalt, pumping, desilting, etc. |
| contractor_id, contractor_name | Fictional contractor |
| assigned_at, work_started_at, completed_at | Timeline |
| area_sqm | Area repaired |
| cost_inr | Amount billed, in rupees. Compare with `rate_card.csv` |
| sla_hours | Target hours from first complaint to completion, by severity (24 h for severity 5 up to 168 h for severity 1) |
| sla_met | Y/N |
| reopened_within_30d | Y if the fix failed within 30 days |
| engineer_remark | Free text |

## rate_card.csv
`repair_method`, `unit` (`per sqm` or `per job`), `standard_rate_inr`. For per sqm methods, expected cost = `area_sqm` x rate. Normal jobs vary roughly 20 to 30% around the rate.

## contractors.csv
`contractor_id`, `contractor_name`, `empanelled_since`, `active_wards`.
