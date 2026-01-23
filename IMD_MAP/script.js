const airports = [
    { name: "Mumbai (CSMIA)", code: "VABB", lat: 19.0896, long: 72.8656, type: "International Hub", wind: "270/12KT", vis: "4000M" },
    { name: "Pune", code: "VAPO", lat: 18.5821, long: 73.9197, type: "Regional", wind: "240/05KT", vis: "8000M" },
    { name: "Nagpur", code: "VANP", lat: 21.0922, long: 79.0472, type: "Regional", wind: "090/08KT", vis: "6000M" },
    { name: "Aurangabad", code: "VAAU", lat: 19.8596, long: 75.3980, type: "Regional", wind: "310/06KT", vis: "9999M" },
    { name: "Nashik (Ozar)", code: "VAOZ", lat: 20.1189, long: 73.9135, type: "Regional", wind: "280/10KT", vis: "7000M" },
    { name: "Kolhapur", code: "VAKP", lat: 16.6636, long: 74.2861, type: "Regional", wind: "250/04KT", vis: "9999M" },
    { name: "Shirdi", code: "VASH", lat: 19.6917, long: 74.3753, type: "Regional", wind: "CALM", vis: "8000M" },
    { name: "Nanded", code: "VAND", lat: 19.1837, long: 77.3190, type: "Regional", wind: "020/03KT", vis: "9999M" },
    { name: "Ratnagiri", code: "VARG", lat: 17.0125, long: 73.3283, type: "Regional", wind: "270/14KT", vis: "5000M" },
    { name: "Sindhudurg", code: "VADW", lat: 16.0028, long: 73.5283, type: "Regional", wind: "240/08KT", vis: "9000M" },
    { name: "Gondia", code: "VAGD", lat: 21.4120, long: 80.1270, type: "Regional", wind: "110/05KT", vis: "9999M" },
    { name: "Goa (Dabolim)", code: "VOGO", lat: 15.3800, long: 73.8333, type: "Regional", wind: "260/15KT", vis: "6000M" }
];

const mumbaiFIR = {
    type: "Feature",
    properties: { name: "Mumbai FIR" },
    geometry: {
        type: "Polygon",
        coordinates: [[
            [79.0819, 25.0003],
            [70.9167, 25.0000],
            [68.1667, 23.6667],
            [68.3833, 23.5000],
            [64.5000, 23.5000],
            [60.0000, 19.8000],
            [60.0000, -6.0000],
            [68.0000, -6.0000],
            [68.0000, 0.0000],
            [70.0000, 3.0833],
            [70.0000, 7.5000],
            [72.0000, 7.5000],
            [72.0000, 15.0000],
            [73.5833, 15.0000],
            [74.0000, 15.5000],
            [77.0000, 17.0000],
            [80.0000, 18.0000],
            [82.0000, 22.0000],
            [79.0819, 25.0003]
        ]]
    }
};

const delhiFIR = {
    type: "Feature",
    properties: { name: "Delhi FIR" },
    geometry: {
        type: "Polygon",
        coordinates: [[
            [79.0819, 25.0003], // Mumbai Border
            [82.0000, 22.0000], // Mumbai/Chennai/Kolkata Junction
            [84.0000, 24.5000], // Approx boundary
            [88.5000, 27.5000], // Nepal/Sikkim area
            [80.0000, 31.0000], // Himalaya
            [79.0000, 33.0000], // Ladakh
            [77.0000, 35.5000], // Northern tip
            [74.0000, 37.0000], // Top
            [72.5000, 34.0000], // West
            [70.0000, 30.0000], // Pakistan Border
            [70.9167, 25.0000], // Mumbai Border start
            [79.0819, 25.0003]  // Close
        ]]
    }
};

const kolkataFIR = {
    type: "Feature",
    properties: { name: "Kolkata FIR" },
    geometry: {
        type: "Polygon",
        coordinates: [[
            [82.0000, 22.0000], // Junction
            [85.0000, 18.0000], // South West corner of Kolkata FIR
            [89.0000, 16.0000], // Bay of Bengal
            [92.0000, 12.0000], // Extent
            [95.0000, 10.0000], // Andaman overlap area?
            [98.0000, 10.0000],
            [98.0000, 28.0000], // East border
            [92.0000, 28.0000],
            [88.5000, 27.5000], // Delhi border
            [84.0000, 24.5000], // Delhi border
            [82.0000, 22.0000]  // Close
        ]]
    }
};

const chennaiFIR = {
    type: "Feature",
    properties: { name: "Chennai FIR" },
    geometry: {
        type: "Polygon",
        coordinates: [[
            [82.0000, 22.0000], // Top Junction
            [80.0000, 18.0000], // Mumbai Border
            [77.0000, 17.0000], // Mumbai Border
            [74.0000, 15.5000], // Mumbai Border
            [73.5833, 15.0000], // Mumbai Border
            [72.0000, 15.0000], // Mumbai Border end
            [72.0000, 8.0000],  // Lakshadweep/Maldives
            [75.0000, 4.0000],  // South
            [90.0000, 4.0000],  // South East
            [92.0000, 12.0000], // Meet Kolkata
            [89.0000, 16.0000], // Meet Kolkata
            [85.0000, 18.0000], // Meet Kolkata
            [82.0000, 22.0000]  // Close
        ]]
    }
};

document.addEventListener("DOMContentLoaded", async () => {
    const mainSvg = d3.select("#main-map");
    const insetSvg = d3.select("#inset-map");

    // Live Clock
    setInterval(() => {
        const clockEl = document.getElementById("clock");
        if (clockEl) clockEl.innerText = new Date().toUTCString().split(' ')[4] + " UTC";
    }, 1000);

    const mapViewport = document.getElementById("map-viewport");
    if (!mapViewport) return;

    const width = mapViewport.clientWidth;
    const height = mapViewport.clientHeight;

    // Projections
    const mainProjection = d3.geoMercator()
        .center([76, 18]) // Centered more on Mumbai FIR
        .scale(800)
        .translate([width / 2, height / 2]);

    const insetProjection = d3.geoMercator()
        .center([76, 18.5])
        .scale(2800)
        .translate([120, 140]);

    const path = d3.geoPath().projection(mainProjection);
    const insetPath = d3.geoPath().projection(insetProjection);

    // Sidebar & Selection Logic
    const airportNavList = d3.select("#airport-nav-list");
    let selectedAirportCode = null;

    const selectAirport = (airport) => {
        selectedAirportCode = airport.code;

        // Update Sidebar
        d3.selectAll("#airport-nav-list li").classed("active", d => d.code === selectedAirportCode);

        // Update Map Pins
        d3.selectAll(".airport-pin").classed("active", d => d.code === selectedAirportCode);

        // Update Info Panel
        document.getElementById("no-selection-msg").classList.add("hidden");
        document.getElementById("airport-details").classList.remove("hidden");
        document.getElementById("det-name").innerText = airport.name;
        document.getElementById("det-code").innerText = airport.code;
        document.getElementById("det-wind").innerText = airport.wind;
        document.getElementById("det-vis").innerText = airport.vis;
        document.getElementById("det-metar").innerText = `METAR ${airport.code} ${new Date().getUTCDay()}${new Date().getUTCHours()}30Z ${airport.wind.replace('/', '')} ${airport.vis.replace('M', '')} HZ NSC 22/16 Q1012 NOSIG`;
    };

    // Load GeoJSON
    try {
        const url = "india_state.geojson";
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Failed to load GeoJSON: ${response.status}`);
        const geoData = await response.json();

        // Populate Sidebar
        airports.forEach(a => {
            const li = airportNavList.append("li")
                .datum(a)
                .on("click", () => selectAirport(a));

            li.html(`<span class="nav-name">${a.name}</span><span class="nav-code">${a.code}</span>`);
        });

        const dropletPath = "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z";

        // Zoom Logic for Main Map
        const zoomLayer = mainSvg.append("g").attr("id", "zoom-container");

        const updateScaleBar = (k) => {
            // Get center coordinate of the map
            const center = mainProjection.invert([width / 2, height / 2]);
            const centerLat = center[1];

            // Calculate real-world distance of 100 pixels at this latitude / zoom
            // With zoom k: 100px on screen -> D / k km

            const p1 = mainProjection.invert([width / 2, height / 2]);
            const p2 = mainProjection.invert([width / 2 + 100 / k, height / 2]);

            if (p1 && p2) {
                const R = 6371;
                const dLat = (p2[1] - p1[1]) * Math.PI / 180;
                const dLon = (p2[0] - p1[0]) * Math.PI / 180;
                const a =
                    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                    Math.cos(p1[1] * Math.PI / 180) * Math.cos(p2[1] * Math.PI / 180) *
                    Math.sin(dLon / 2) * Math.sin(dLon / 2);
                const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
                const d = R * c; // Actual distance represented by 100 screen pixels

                const niceNumbers = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000];
                let displayKm = 500;
                let displayPx = 100;

                for (let num of niceNumbers) {
                    // how many pixels for 'num' km?
                    // d km = 100 px
                    // num km = (100 * num / d) px
                    const px = (100 * num) / d;
                    if (px >= 60 && px <= 180) { // wider range to allow finding a match
                        displayKm = num;
                        displayPx = px;
                        break;
                    }
                }

                const scaleBarLine = document.getElementById("scale-bar-line");
                const scaleBarText = document.getElementById("scale-bar-text");
                if (scaleBarLine && scaleBarText) {
                    scaleBarLine.style.width = `${displayPx}px`;
                    scaleBarText.innerText = `${displayKm} km`;
                }
            }
        };

        const zoom = d3.zoom()
            .scaleExtent([0.5, 8])
            .on("zoom", (event) => {
                zoomLayer.attr("transform", event.transform);
                updateScaleBar(event.transform.k);
            });

        mainSvg.call(zoom);

        const renderMap = (svgContainer, projection, geoPath, isInset = false) => {
            // If it's the main map, we render into the zoomLayer instead of the SVG directly
            const target = isInset ? svgContainer.append("g") : zoomLayer;

            const stateGroup = target.append("g");

            // Draw states
            stateGroup.selectAll(".state-color")
                .data(geoData.features)
                .enter()
                .append("path")
                .attr("d", geoPath)
                .attr("class", "state-color muted"); // All muted

            // Draw FIRs (Only on main map)
            if (!isInset) {
                const firs = [
                    { data: mumbaiFIR, class: "fir-mumbai" },
                    { data: delhiFIR, class: "fir-delhi" },
                    { data: kolkataFIR, class: "fir-kolkata" },
                    { data: chennaiFIR, class: "fir-chennai" }
                ];

                firs.forEach(fir => {
                    target.append("path")
                        .datum(fir.data)
                        .attr("d", geoPath)
                        .attr("class", `fir-boundary ${fir.class}`);
                });
            }

            // Draw State Names
            const labelGroup = target.append("g").attr("class", "state-label-group");
            labelGroup.selectAll(".state-map-label")
                .data(geoData.features)
                .enter()
                .append("text")
                .attr("class", "state-map-label muted")
                .attr("transform", d => {
                    const centroid = projection(d3.geoCentroid(d));
                    return centroid ? `translate(${centroid[0]}, ${centroid[1]})` : null;
                })
                .attr("text-anchor", "middle")
                .attr("font-size", isInset ? "12px" : "8px")
                .text(d => d.properties.NAME_1 || d.properties.st_nm || d.properties.NAME);

            // Graticule
            const graticule = d3.geoGraticule().step([5, 5]);
            target.append("path")
                .datum(graticule)
                .attr("class", "graticule")
                .attr("d", geoPath);

            // Pins
            const pinGroup = target.append("g");
            airports.forEach(a => {
                const coords = projection([a.long, a.lat]);
                if (!coords) return;

                const pin = pinGroup.append("g")
                    .datum(a)
                    .attr("class", `airport-pin ${a.code === 'VABB' ? 'hub' : ''}`)
                    .attr("id", `pin-${a.code}-${isInset ? 'inset' : 'main'}`)
                    .attr("transform", `translate(${coords[0]}, ${coords[1]}) scale(${isInset ? 1.2 : 0.8})`)
                    .on("click", () => {
                        console.log(`Pin Clicked: ${a.code}`);
                        const mainPin = d3.select(`#pin-${a.code}-main`);

                        // If pin is red (warning), navigate to dashboard
                        if (mainPin.classed("warning")) {
                            window.open('/pages/dashboard', '_blank');
                            return;
                        }

                        selectAirport(a);
                    });

                const pinBody = pin.append("g").attr("class", "pin-body");
                pinBody.append("circle").attr("class", "sonar").attr("cx", 0).attr("cy", -13).attr("r", 0);
                pinBody.append("path")
                    .attr("class", "droplet-path")
                    .attr("d", dropletPath)
                    .attr("transform", "translate(-12, -22)");
                pinBody.append("circle")
                    .attr("class", "pin-center")
                    .attr("cx", 0)
                    .attr("cy", -13)
                    .attr("r", 3);

                pin.append("text")
                    .attr("class", "airport-label")
                    .attr("dx", 0)
                    .attr("dy", -28)
                    .attr("text-anchor", "middle")
                    .text(isInset ? a.name : a.code);
            });
        };

        renderMap(mainSvg, mainProjection, path);
        // Also render inset map
        renderMap(insetSvg, insetProjection, insetPath, true);

        // Map Interaction events
        d3.select("#zoom-in").on("click", () => {
            mainSvg.transition().duration(400).call(zoom.scaleBy, 1.5);
        });

        d3.select("#zoom-out").on("click", () => {
            mainSvg.transition().duration(400).call(zoom.scaleBy, 0.6);
        });

        d3.select("#zoom-reset").on("click", () => {
            mainSvg.transition().duration(750)
                .call(zoom.transform, d3.zoomIdentity);
        });

        // Initializes Scale Bar (initial k=1)
        updateScaleBar(1);

        // Fetch Live Warnings
        const fetchActiveWarnings = async () => {
            try {
                const response = await fetch('/alerts/map');
                if (!response.ok) return;
                const alerts = await response.json();

                // Reset all warnings first
                d3.selectAll(".airport-pin").classed("warning", false).classed("flicker", false);

                const now = new Date().getTime();

                alerts.forEach(alert => {
                    // Assuming alert object has station_code and valid_until (ISO string)
                    const code = alert.station_code;
                    console.log(`DEBUG: Processing alert for ${code}`);

                    let expiryTime = 0;
                    if (alert.content && alert.content.valid_until_iso) {
                        expiryTime = new Date(alert.content.valid_until_iso).getTime();
                    }

                    const timeLeft = expiryTime - now;

                    // Add warning class to main and inset pins
                    d3.selectAll(`.airport-pin[id*="${code}"]`).classed("warning", true);

                    // Add flicker if < 30 mins left (30 * 60 * 1000 = 1800000ms)
                    if (timeLeft > 0 && timeLeft < 1800000) {
                        d3.selectAll(`.airport-pin[id*="${code}"]`).classed("flicker", true);
                    }
                });

            } catch (err) {
                console.error("Error fetching alerts:", err);
            }
        };

        // Initial fetch and poll every 2s for real-time updates
        fetchActiveWarnings();
        setInterval(fetchActiveWarnings, 2000);

    } catch (err) {
        console.error("Dashboard error:", err);
    }
});