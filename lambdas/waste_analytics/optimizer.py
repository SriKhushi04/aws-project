"""Route optimization using Haversine distance, Nearest-Neighbour, and 2-Opt TSP heuristics."""
from typing import List, Dict, Any, Tuple
from lambdas.common.utils import calculate_haversine_distance

def compute_total_tour_distance(tour: List[Dict[str, Any]]) -> float:
    """Calculate the total circular distance in kilometers for a tour."""
    if len(tour) < 2:
        return 0.0

    total_dist = 0.0
    for i in range(len(tour) - 1):
        d = calculate_haversine_distance(
            tour[i]["latitude"], tour[i]["longitude"],
            tour[i + 1]["latitude"], tour[i + 1]["longitude"]
        )
        total_dist += d
    return total_dist

def nearest_neighbour_tour(
    depot: Dict[str, Any],
    bins: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Construct an initial closed tour starting at depot, visiting all bins, and returning to depot.
    """
    if not bins:
        return [depot, depot]

    unvisited = list(bins)
    tour = [depot]
    current = depot

    while unvisited:
        # Find closest unvisited bin to current node
        nearest_bin = None
        min_dist = float("inf")

        for b in unvisited:
            dist = calculate_haversine_distance(
                current["latitude"], current["longitude"],
                b["latitude"], b["longitude"]
            )
            if dist < min_dist:
                min_dist = dist
                nearest_bin = b

        tour.append(nearest_bin)
        unvisited.remove(nearest_bin)
        current = nearest_bin

    # Close the loop by returning to depot
    tour.append(depot)
    return tour

def two_opt_optimize(tour: List[Dict[str, Any]], max_iterations: int = 100) -> List[Dict[str, Any]]:
    """
    Improve an existing tour by iteratively reversing sub-tours to eliminate crossing edges.
    The tour must start and end at the depot: [DEPOT, B1, B2, ..., Bn, DEPOT].
    """
    n = len(tour)
    # A tour of fewer than 4 nodes (e.g. DEPOT -> B1 -> DEPOT has 3 nodes) cannot be 2-opt improved
    if n < 4:
        return tour

    best_tour = list(tour)
    improved = True
    iterations = 0

    while improved and iterations < max_iterations:
        improved = False
        iterations += 1

        for i in range(1, n - 2):
            for j in range(i + 1, n - 1):
                # Nodes: A = best_tour[i-1], B = best_tour[i], C = best_tour[j], D = best_tour[j+1]
                node_a = best_tour[i - 1]
                node_b = best_tour[i]
                node_c = best_tour[j]
                node_d = best_tour[j + 1]

                current_dist = (
                    calculate_haversine_distance(node_a["latitude"], node_a["longitude"], node_b["latitude"], node_b["longitude"]) +
                    calculate_haversine_distance(node_c["latitude"], node_c["longitude"], node_d["latitude"], node_d["longitude"])
                )

                new_dist = (
                    calculate_haversine_distance(node_a["latitude"], node_a["longitude"], node_c["latitude"], node_c["longitude"]) +
                    calculate_haversine_distance(node_b["latitude"], node_b["longitude"], node_d["latitude"], node_d["longitude"])
                )

                # If reversing sub-tour [i..j] saves distance
                if new_dist < current_dist - 1e-6:
                    best_tour[i : j + 1] = reversed(best_tour[i : j + 1])
                    improved = True
                    break
            if improved:
                break

    return best_tour

def solve_collection_route(
    depot: Dict[str, Any],
    selected_bins: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate an optimized collection route visiting selected bins starting and returning to depot.
    """
    if not selected_bins:
        return {
            "depot": depot,
            "total_distance_km": 0.0,
            "num_bins_serviced": 0,
            "stops": []
        }

    # 1. Construct initial tour via Nearest-Neighbour
    initial_tour = nearest_neighbour_tour(depot, selected_bins)
    nn_distance = compute_total_tour_distance(initial_tour)

    # 2. Optimize tour via 2-Opt
    optimized_tour = two_opt_optimize(initial_tour)
    optimized_distance = compute_total_tour_distance(optimized_tour)

    # 3. Format stops for API / Dashboard consumption
    stops: List[Dict[str, Any]] = []
    # Skip the starting and ending depot entries when numbering collection stops
    for stop_idx, node in enumerate(optimized_tour[1:-1], start=1):
        stops.append({
            "stop_number": stop_idx,
            "bin_id": node["bin_id"],
            "location_name": node.get("location_name", ""),
            "latitude": node["latitude"],
            "longitude": node["longitude"],
            "fill_level": node.get("fill_level", 0.0),
            "priority_score": node.get("priority_score", 0.0),
            "predicted_hours_to_90": node.get("predicted_hours_to_90")
        })

    return {
        "depot": depot,
        "initial_distance_km": round(nn_distance, 2),
        "total_distance_km": round(optimized_distance, 2),
        "num_bins_serviced": len(selected_bins),
        "stops": stops
    }

