// Data storage
let departmentsData = {};
let regionsData = {};
let genderStats = {};
let candidateStats = {};
let timelineData = [];
let deptSortMode = 'gap-desc'; // 'gap-desc', 'gap-asc', 'alpha'
let regionSortMode = 'gap-desc';
let lockedDept = null;
let lockedRegion = null;
let deptElements = {}; // Store D3 selections for highlighting
let regionElements = {};

async function init() {
    await loadData();
    populateDepartmentList();
    populateRegionList();
    renderGenderCharts();
    renderCandidateCharts();
    await createMaps();
}

async function loadData() {
    try {
        console.log('Loading departments data...');
        const deptResponse = await fetch('departments_data.json');
        if (!deptResponse.ok) throw new Error(`HTTP ${deptResponse.status}`);
        departmentsData = (await deptResponse.json()).departments;
        console.log(`Loaded ${Object.keys(departmentsData).length} departments`);

        console.log('Loading regions data...');
        const regResponse = await fetch('regions_data.json');
        if (!regResponse.ok) throw new Error(`HTTP ${regResponse.status}`);
        regionsData = (await regResponse.json()).regions;
        console.log(`Loaded ${Object.keys(regionsData).length} regions`);

        console.log('Loading gender stats...');
        const genderResponse = await fetch('gender_stats.json', { cache: 'no-store' });
        if (!genderResponse.ok) throw new Error(`HTTP ${genderResponse.status}`);
        genderStats = (await genderResponse.json()).stats;
        console.log('Loaded gender statistics');

        const candidateResponse = await fetch('candidate_stats.json', { cache: 'no-store' });
        if (!candidateResponse.ok) throw new Error(`HTTP ${candidateResponse.status}`);
        candidateStats = await candidateResponse.json();
        const timelineResponse = await fetch('timeline_data.json', { cache: 'no-store' });
        if (!timelineResponse.ok) throw new Error(`HTTP ${timelineResponse.status}`);
        timelineData = (await timelineResponse.json()).seasons;
    } catch (error) {
        console.error('Error loading data:', error);
        document.querySelectorAll('#timeline, #ranking, #returnee-flow, #gender-charts, #age-charts, #first-out-charts, #finale-charts, #choice-charts, #returnee-charts, #allstar-age-charts, #allstar-gender-charts, #allstar-finale-charts').forEach(container => {
            container.textContent = 'Impossible de charger les données. Vérifiez que les fichiers JSON sont disponibles.';
        });
        throw error;
    }
}

function getColor(gap, candidates, isRegion = false) {
    if (candidates === 0) return '#ffffff';
    
    if (isRegion) {
        if (gap > 1.5) return '#1a9850';
        if (gap > 0.5) return '#66bd63';
        if (gap >= 0) return '#b1d582';
        if (gap > -0.5) return '#fddbc7';
        if (gap > -1.5) return '#ef8a62';
        return '#d73027';
    } else {
        if (gap > 0.5) return '#1a9850';
        if (gap > 0.2) return '#66bd63';
        if (gap >= 0) return '#b1d582';
        if (gap > -0.2) return '#fddbc7';
        if (gap > -0.5) return '#ef8a62';
        return '#d73027';
    }
}

// Sort menu functions
function toggleDeptSortMenu(event) {
    event.stopPropagation();
    const menu = document.getElementById('dept-sort-menu');
    menu.classList.toggle('open');
    document.addEventListener('click', closeDeptSortMenu);
}

function closeDeptSortMenu() {
    document.getElementById('dept-sort-menu').classList.remove('open');
    document.removeEventListener('click', closeDeptSortMenu);
}

function setDeptSort(mode) {
    deptSortMode = mode;
    
    // Update label
    const labels = { 'gap-desc': 'Gap ↓', 'gap-asc': 'Gap ↑', 'alpha': 'A → Z' };
    document.getElementById('dept-sort-label').textContent = labels[mode];
    
    // Update menu
    document.querySelectorAll('#dept-sort-menu .sort-item').forEach((item, idx) => {
        item.classList.remove('active');
        if ((mode === 'gap-desc' && idx === 0) ||
            (mode === 'gap-asc' && idx === 1) ||
            (mode === 'alpha' && idx === 2)) {
            item.classList.add('active');
        }
    });
    
    closeDeptSortMenu();
    populateDepartmentList();
}

function toggleRegionSortMenu(event) {
    event.stopPropagation();
    const menu = document.getElementById('region-sort-menu');
    menu.classList.toggle('open');
    document.addEventListener('click', closeRegionSortMenu);
}

function closeRegionSortMenu() {
    document.getElementById('region-sort-menu').classList.remove('open');
    document.removeEventListener('click', closeRegionSortMenu);
}

function setRegionSort(mode) {
    regionSortMode = mode;
    
    // Update label
    const labels = { 'gap-desc': 'Gap ↓', 'gap-asc': 'Gap ↑', 'alpha': 'A → Z' };
    document.getElementById('region-sort-label').textContent = labels[mode];
    
    // Update menu
    document.querySelectorAll('#region-sort-menu .sort-item').forEach((item, idx) => {
        item.classList.remove('active');
        if ((mode === 'gap-desc' && idx === 0) ||
            (mode === 'gap-asc' && idx === 1) ||
            (mode === 'alpha' && idx === 2)) {
            item.classList.add('active');
        }
    });
    
    closeRegionSortMenu();
    populateRegionList();
}

function sortData(entries, mode) {
    if (mode === 'gap-desc') {
        return entries.sort((a, b) => b[1].gap_percentage - a[1].gap_percentage);
    } else if (mode === 'gap-asc') {
        return entries.sort((a, b) => a[1].gap_percentage - b[1].gap_percentage);
    } else if (mode === 'alpha') {
        return entries.sort((a, b) => a[0].localeCompare(b[0]));
    }
    return entries;
}

function populateDepartmentList() {
    const list = document.getElementById('dept-list');
    let depts = Object.entries(departmentsData);
    
    depts = sortData(depts, deptSortMode);
    
    let html = '';
    for (const [name, data] of depts) {
        const color = getColor(data.gap_percentage, data.candidate_count);
        const isLocked = lockedDept === name;
        html += `
            <div class="dept-item ${isLocked ? 'locked' : ''}" onclick="selectDept(event, '${name.replace(/'/g, "\\'")}')">
                <div>
                    <div class="dept-name">${name}</div>
                    <div class="dept-gap">Gap: ${data.gap_percentage > 0 ? '+' : ''}${data.gap_percentage}%</div>
                </div>
                <div class="dept-color" style="background: ${color};"></div>
            </div>
        `;
    }
    list.innerHTML = html;
}

function populateRegionList() {
    const list = document.getElementById('region-list');
    let regions = Object.entries(regionsData);
    
    regions = sortData(regions, regionSortMode);
    
    let html = '';
    for (const [name, data] of regions) {
        const color = getColor(data.gap_percentage, data.candidate_count, true);
        const isLocked = lockedRegion === name;
        html += `
            <div class="dept-item ${isLocked ? 'locked' : ''}" onclick="selectRegion(event, '${name.replace(/'/g, "\\'")}')">
                <div>
                    <div class="dept-name">${name}</div>
                    <div class="dept-gap">Gap: ${data.gap_percentage > 0 ? '+' : ''}${data.gap_percentage}%</div>
                </div>
                <div class="dept-color" style="background: ${color};"></div>
            </div>
        `;
    }
    list.innerHTML = html;
}

function selectDept(event, name) {
    event.stopPropagation();
    lockedDept = lockedDept === name ? null : name;
    showDeptInfo(name);
    highlightDeptOnMap(name);
    populateDepartmentList();
}

function selectRegion(event, name) {
    event.stopPropagation();
    lockedRegion = lockedRegion === name ? null : name;
    showRegionInfo(name);
    highlightRegionOnMap(name);
    populateRegionList();
}

function showDeptInfo(name) {
    const data = departmentsData[name];
    if (!data) return;

    let html = `${lockedDept === name ? '<div class="locked-label">VERROUILLÉ - Cliquer pour déverrouiller</div>' : ''}
        <div class="info-row">
            <span class="label">Département:</span>
            <span class="value"><strong>${name}</strong></span>
        </div>
        <div class="info-row">
            <span class="label">Population:</span>
            <span class="value">${data.population_percentage}%</span>
        </div>
        <div class="info-row">
            <span class="label">Candidats:</span>
            <span class="value">${data.candidate_count}</span>
        </div>
        <div class="info-row">
            <span class="label">% Candidats:</span>
            <span class="value">${data.candidate_percentage}%</span>
        </div>
        <div class="info-row">
            <span class="label">Gap:</span>
            <span class="value gap-value" style="color: ${data.candidate_count === 0 ? '#555' : getColor(data.gap_percentage, data.candidate_count)}; font-weight: bold;">
                ${data.gap_percentage > 0 ? '+' : ''}${data.gap_percentage}%
            </span>
        </div>
    `;

    if (data.candidates && data.candidates.length > 0) {
        html += `
            <div class="candidates-list">
                <h4>Candidats (${data.candidates.length})</h4>
                ${data.candidates.map(c => `<div class="candidate-name">• ${typeof c === 'object' ? c.name + ' (' + c.season + ')' : c}</div>`).join('')}
            </div>
        `;
    }

    document.getElementById('dept-info').innerHTML = html;
}

function showRegionInfo(name) {
    const data = regionsData[name];
    if (!data) return;

    let html = `${lockedRegion === name ? '<div class="locked-label">VERROUILLÉ - Cliquer pour déverrouiller</div>' : ''}
        <div class="info-row">
            <span class="label">Région:</span>
            <span class="value"><strong>${name}</strong></span>
        </div>
        <div class="info-row">
            <span class="label">Population:</span>
            <span class="value">${data.population_percentage}%</span>
        </div>
        <div class="info-row">
            <span class="label">Candidats:</span>
            <span class="value">${data.candidate_count}</span>
        </div>
        <div class="info-row">
            <span class="label">% Candidats:</span>
            <span class="value">${data.candidate_percentage}%</span>
        </div>
        <div class="info-row">
            <span class="label">Gap:</span>
            <span class="value gap-value" style="color: ${data.candidate_count === 0 ? '#555' : getColor(data.gap_percentage, data.candidate_count, true)}; font-weight: bold;">
                ${data.gap_percentage > 0 ? '+' : ''}${data.gap_percentage}%
            </span>
        </div>
    `;

    if (data.candidates && data.candidates.length > 0) {
        html += `
            <div class="candidates-list">
                <h4>Candidats (${data.candidates.length})</h4>
                ${data.candidates.map(c => `<div class="candidate-name">• ${typeof c === 'object' ? c.name + ' (' + c.season + ')' : c}</div>`).join('')}
            </div>
        `;
    }

    document.getElementById('region-info').innerHTML = html;
}

function highlightDeptOnMap(name) {
    // Remove highlight from all
    d3.selectAll('.department').classed('highlighted-region', false);
    // Add highlight to selected
    if (lockedDept) {
        d3.selectAll('.department').filter(d => d.properties.nom === lockedDept).classed('highlighted-region', true);
    }
}

function highlightRegionOnMap(name) {
    // Remove highlight from all
    d3.selectAll('.region').classed('highlighted-region', false);
    // Add highlight to selected
    if (lockedRegion) {
        d3.selectAll('.region').filter(d => d.properties.nom === lockedRegion).classed('highlighted-region', true);
    }
}

async function createMaps() {
    await createDeptMap();
    await createRegionMap();
    await createTribeMaps();
}

const TRIBE_COLORS = {
    Bleu: '#00C2D1',
    Orange: '#FE7F2D',
    Vert: '#6DA34D',
    Violet: '#827191'
};

const GENDER_COLORS = { F: '#1b998b', H: '#58355e' };

function ensureDefs(svg) {
    let defs = svg.select('defs');
    return defs.empty() ? svg.append('defs') : defs;
}

function hatchPattern(defs, colors) {
    const id = `hatch-${colors.join('-')}`;
    if (!defs.select(`#${id}`).empty()) return `url(#${id})`;
    const size = 6;
    const stripe = size / colors.length;
    const pattern = defs.append('pattern')
        .attr('id', id)
        .attr('patternUnits', 'userSpaceOnUse')
        .attr('width', size)
        .attr('height', size)
        .attr('patternTransform', 'rotate(45)');
    colors.forEach((c, i) => {
        pattern.append('rect')
            .attr('x', i * stripe).attr('y', 0)
            .attr('width', stripe).attr('height', size)
            .attr('fill', TRIBE_COLORS[c]);
    });
    return `url(#${id})`;
}

function dotPattern(defs, color) {
    const id = `dots-${color}`;
    if (!defs.select(`#${id}`).empty()) return `url(#${id})`;
    const pattern = defs.append('pattern')
        .attr('id', id)
        .attr('patternUnits', 'userSpaceOnUse')
        .attr('width', 6)
        .attr('height', 6);
    pattern.append('rect').attr('width', 6).attr('height', 6).attr('fill', '#ffffff');
    pattern.append('circle').attr('cx', 3).attr('cy', 3).attr('r', 1.5).attr('fill', TRIBE_COLORS[color]);
    return `url(#${id})`;
}

async function createTribeMaps() {
    try {
        const [tribes, deptGeo, regGeo] = await Promise.all([
            fetch('tribes_data.json').then(r => r.json()),
            fetch('https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson').then(r => r.json()),
            fetch('https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/regions.geojson').then(r => r.json())
        ]);

        renderTribeMap('map-tribe-dept', deptGeo, (name, defs) => {
            const info = tribes.departments[name];
            if (!info) return '#cccccc';
            if (info.colors.length === 1) return TRIBE_COLORS[info.colors[0]];
            if (info.colors.length > 1) return hatchPattern(defs, info.colors);
            return info.fallback ? dotPattern(defs, info.fallback) : '#ffffff';
        });

        renderTribeMap('map-tribe-region', regGeo, (name, defs) => {
            const colors = tribes.regions[name] || [];
            if (colors.length === 0) return '#ffffff';
            if (colors.length === 1) return TRIBE_COLORS[colors[0]];
            return hatchPattern(defs, colors);
        });
    } catch (error) {
        console.error('Error loading tribe maps:', error);
        for (const id of ['map-tribe-dept', 'map-tribe-region']) {
            document.getElementById(id).textContent = 'Impossible de charger la carte géographique.';
        }
    }
}

function renderTribeMap(containerId, geojson, fillFn) {
    const container = document.getElementById(containerId);
    const width = container.clientWidth;
    const height = container.clientHeight;

    const svg = d3.select(`#${containerId}`)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`);
    const defs = ensureDefs(svg);

    const projection = d3.geoMercator().fitSize([width, height], geojson);
    const pathGen = d3.geoPath().projection(projection);
    const g = svg.append('g');

    g.selectAll('path')
        .data(geojson.features)
        .enter()
        .append('path')
        .attr('d', pathGen)
        .attr('fill', d => fillFn(d.properties.nom, defs))
        .attr('stroke', '#666')
        .attr('stroke-width', 0.5)
        .append('title')
        .text(d => d.properties.nom);

    addMapZoom(container, svg, g);
}

function addMapZoom(container, svg, group) {
    const zoom = d3.zoom().scaleExtent([1, 8]).on('zoom', event => {
        group.attr('transform', event.transform);
        group.selectAll('.map-sign')
            .attr('font-size', d => d.signSize / Math.sqrt(event.transform.k))
            .style('stroke-width', `${3 / Math.sqrt(event.transform.k)}px`);
    });
    svg.call(zoom).on('wheel.zoom', null).on('dblclick.zoom', null);
    const controls = document.createElement('div');
    controls.className = 'map-zoom';
    for (const [label, factor, title] of [['+', 1.5, 'Zoomer'], ['−', 1 / 1.5, 'Dézoomer']]) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = label;
        button.setAttribute('aria-label', title);
        button.addEventListener('click', () => svg.call(zoom.scaleBy, factor));
        controls.appendChild(button);
    }
    container.appendChild(controls);
}

async function createDeptMap() {
    try {
        const response = await fetch('https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson');
        const geojson = await response.json();
        renderMap('map-dept', geojson, 'department');
    } catch (error) {
        console.error('Error loading dept map:', error);
        document.getElementById('map-dept').textContent = 'Impossible de charger la carte géographique.';
    }
}

async function createRegionMap() {
    try {
        const response = await fetch('https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/regions.geojson');
        const geojson = await response.json();
        renderMap('map-region', geojson, 'region');
    } catch (error) {
        console.error('Error loading region map:', error);
        document.getElementById('map-region').textContent = 'Impossible de charger la carte géographique.';
    }
}

function renderMap(containerId, geojson, type) {
    const container = document.getElementById(containerId);
    const width = container.clientWidth;
    const height = container.clientHeight;

    console.log(`Rendering ${type} map, ${geojson.features.length} features`);

    const svg = d3.select(`#${containerId}`)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`);

    const projection = d3.geoMercator().fitSize([width, height], geojson);
    const pathGen = d3.geoPath().projection(projection);

    const g = svg.append('g');

    let coloredCount = 0;
    let greyCount = 0;

    g.selectAll(`.${type}`)
        .data(geojson.features)
        .enter()
        .append('path')
        .attr('class', type)
        .attr('d', pathGen)
        .attr('fill', (d) => {
            const dataSource = type === 'department' ? departmentsData : regionsData;
            const name = d.properties.nom;
            const data = dataSource[name];
            
            if (!data) {
                greyCount++;
                console.warn(`No data for ${type}: ${name}`);
                return '#cccccc';
            }
            
            coloredCount++;
            const isRegion = type === 'region';
            const color = getColor(data.gap_percentage, data.candidate_count, isRegion);
            return color;
        })
        .on('click', function(event, d) {
            event.stopPropagation();
            if (type === 'department') {
                selectDept(event, d.properties.nom);
            } else {
                selectRegion(event, d.properties.nom);
            }
        })
        .on('mouseover', function(event, d) {
            if (type === 'department' && lockedDept) {
                // Don't show hover when locked
                return;
            }
            if (type === 'region' && lockedRegion) {
                // Don't show hover when locked
                return;
            }
            
            d3.select(this).style('stroke', '#2d7d4f').style('stroke-width', '1.5px');
            if (type === 'department') {
                showDeptInfo(d.properties.nom);
            } else {
                showRegionInfo(d.properties.nom);
            }
        })
        .on('mouseout', function() {
            d3.select(this).style('stroke', '#999').style('stroke-width', '0.5px');
            if (type === 'department' && lockedDept) {
                showDeptInfo(lockedDept);
            } else if (type === 'region' && lockedRegion) {
                showRegionInfo(lockedRegion);
            }
        });

    const dataSource = type === 'department' ? departmentsData : regionsData;
    g.selectAll('.map-sign').data(geojson.features.filter(d => dataSource[d.properties.nom]).map(d => ({
        ...d,
        signSize: Math.min(14, 6 + Math.sqrt(Math.abs(dataSource[d.properties.nom].gap_percentage)) * 4)
    })))
        .join('text').attr('class', 'map-sign')
        .attr('x', d => pathGen.centroid(d)[0]).attr('y', d => pathGen.centroid(d)[1])
        .attr('font-size', d => d.signSize)
        .text(d => dataSource[d.properties.nom].gap_percentage > 0 ? '+' : '−');
    console.log(`${type} map: ${coloredCount} colored, ${greyCount} grey`);
    addMapZoom(container, svg, g);
}

function renderGenderCharts(container = document.getElementById('gender-charts'), statsData = genderStats, definitions = null) {
    if (!container || !statsData || Object.keys(statsData).length === 0) {
        console.warn('Cannot render gender charts');
        return;
    }

    const chartDefinitions = definitions || [
        {
            key: 'overall',
            title: 'Ensemble des candidats',
            subtitle: '(tous les candidats et candidates)'
        },
        {
            key: 'ori',
            title: 'Orientation',
            subtitle: '(où ORI? == Oui)'
        },
        {
            key: 'pot',
            title: 'Les Poteaux',
            subtitle: '(où POT? == Oui)'
        },
        {
            key: 'place',
            title: 'Gagnants',
            subtitle: '(où PLACE == 1)'
        }
    ];

    chartDefinitions.forEach(def => {
        const stats = statsData[def.key];
        if (!stats) return;

        const chart = document.createElement('div');
        chart.className = 'gender-chart';
        
        const h = stats.H || 0;
        const f = stats.F || 0;
        const total = stats.total == null ? h + f : stats.total;
        
        const hPercent = total > 0 ? ((h / total) * 100).toFixed(1) : 0;
        const fPercent = total > 0 ? ((f / total) * 100).toFixed(1) : 0;
        
        // Calculate bar heights (max height = 150px, min = 10px)
        const maxValue = Math.max(h, f, 1);
        const hHeight = Math.max(10, (h / maxValue) * 150);
        const fHeight = Math.max(10, (f / maxValue) * 150);
        
        chart.innerHTML = `
            <h3>${def.title}</h3>
            <div class="chart-bars">
                <div class="bar-container">
                    <div class="bar" style="height: ${hHeight}px;"></div>
                    <div class="bar-label">Hommes</div>
                    <div class="bar-count">${h}</div>
                </div>
                <div class="bar-container">
                    <div class="bar female" style="height: ${fHeight}px;"></div>
                    <div class="bar-label">Femmes</div>
                    <div class="bar-count">${f}</div>
                </div>
            </div>
            <div class="chart-stats">
                <div>
                    <span>Hommes:</span>
                    <strong>${hPercent}%</strong>
                </div>
                <div>
                    <span>Femmes:</span>
                    <strong>${fPercent}%</strong>
                </div>
                <div style="border-top: 1px solid #ddd; margin-top: 8px; padding-top: 8px;">
                    <span>Total:</span>
                    <strong>${total} candidat${total > 1 ? 's' : ''}</strong>
                </div>
            </div>
        `;
        if (def.names) {
            for (const [index, gender] of ['H', 'F'].entries()) {
                const bar = chart.querySelectorAll('.bar')[index];
                const names = def.names[gender].map(candidate => `${candidate.nom} (${candidate.saison})`).join(', ');
                bar.title = names || 'Aucun candidat';
                bar.tabIndex = 0;
                bar.setAttribute('aria-label', `${gender === 'F' ? 'Femmes' : 'Hommes'} : ${names || 'aucun candidat'}`);
            }
        }
        
        container.appendChild(chart);
    });
}

function renderCandidateCharts() {
    const ages = document.getElementById('age-charts');
    renderAgeChart(ages, 'Âge de tous les candidats', candidateStats.ages.all, candidateStats.age_candidates.all);
    renderAgeChart(ages, "Âge des candidats ayant atteint l'épreuve d'orientation", candidateStats.ages.orientation, candidateStats.age_candidates.orientation);
    renderAgeSummary(ages);
    renderAgeRates(ages);
    renderTimeline();
    renderRanking();
    renderReturneeFlow();
    renderFinaleCharts();
    renderChoiceCharts();
    renderReturnees();
    renderAllStarCharts();

    const firstOuts = candidateStats.first_outs;
    const charts = document.getElementById('first-out-charts');
    const genderEntries = [
        { label: 'Femmes', value: firstOuts.gender.F, color: GENDER_COLORS.F },
        { label: 'Hommes', value: firstOuts.gender.H, color: GENDER_COLORS.H }
    ];
    if (firstOuts.gender.unknown) {
        genderEntries.push({ label: 'Non renseigné', value: firstOuts.gender.unknown, color: '#999999' });
    }
    const genderChart = document.createElement('div');
    genderChart.className = 'first-out-gender-chart';
    charts.appendChild(genderChart);
    renderPie(genderChart, 'Répartition par genre des premiers éliminés', genderEntries);
    for (const [gender, label] of [['F', 'femmes'], ['H', 'hommes']]) {
        const section = document.createElement('section');
        section.className = 'pie-comparison-section';
        const heading = document.createElement('h3');
        heading.textContent = `Répartition des âges : ${label}`;
        const pair = document.createElement('div');
        pair.className = 'pie-comparison';
        section.append(heading, pair);
        charts.appendChild(section);
        renderPie(pair, gender === 'F' ? 'Premières éliminées' : 'Premiers éliminés', groupAges(firstOuts.ages[gender].counts), 'pie-comparison-chart');
        renderPie(pair, 'Toutes les participations', groupAges(candidateStats.ages.all[gender].counts), 'pie-comparison-chart');
    }
}

function renderTimeline() {
    const container = document.getElementById('timeline');
    const years = d3.group(timelineData, season => season.start_date.slice(0, 4));
    for (const [year, seasons] of years) {
        const column = document.createElement('div');
        column.className = 'timeline-year';
        const heading = document.createElement('strong');
        heading.textContent = year;
        column.appendChild(heading);
        for (const season of seasons) {
            const item = document.createElement('div');
            item.className = `timeline-season${season.series === 'all_stars' ? ' allstar' : ''}`;
            item.textContent = season.name;
            const count = document.createElement('small');
            count.textContent = `${season.candidate_count} candidat${season.candidate_count === 1 ? '' : 's'}`;
            item.appendChild(count);
            item.title = `${season.start_date} – ${season.end_date}`;
            column.appendChild(item);
        }
        container.appendChild(column);
    }
}

function renderRanking() {
    const container = document.getElementById('ranking');
    const candidates = candidateStats.returnee_ranking.candidates;
    const note = document.createElement('p');
    note.className = 'chart-note';
    note.textContent = "Les retours non identifiés sont exclus. L'écart entre orientations utilise les dates de début des saisons, faute de dates d'épreuve. Les participations aux saisons non terminées sont comptées dès que la place ou l'orientation est connue ; les indicateurs vides des saisons terminées sont considérés comme négatifs. Pour les classements manquants lors d'un retour, seule la meilleure place connue est utilisée.";
    container.appendChild(note);
    const list = document.createElement('ol');
    list.className = 'ranking';
    for (const candidate of candidates) {
        const item = document.createElement('li');
        const heading = document.createElement('strong');
        heading.className = 'ranking-name';
        heading.textContent = `${candidate.rank === 1 ? '🏅 ' : ''}${candidate.rank}. ${candidate.nom.trim()}`;
        const rate = candidate.orientation_access_rate === null ? 'non disponible' :
            `${(100 * candidate.orientation_access_rate).toFixed(1).replace('.', ',')} %`;
        const metrics = document.createElement('div');
        metrics.className = 'ranking-metrics';
        const values = [
            `${candidate.wins} victoire(s)`,
            `Orientation : ${rate} (${candidate.orientation_count}/${candidate.eligible_appearances})`
        ];
        if (candidate.best_comeback_place_tiebreak_applied) {
            const place = candidate.best_comeback_place === null ? 'inconnu' :
                formatPlacement({ place: candidate.best_comeback_place });
            const missing = candidate.comeback_appearances_without_placement ?
                ` (${candidate.comeback_appearances_without_placement} classement(s) manquant(s))` : '';
            values.push(`Meilleur retour : ${place}${missing}`);
        }
        for (const value of values) {
            const metric = document.createElement('span');
            metric.textContent = value;
            metrics.appendChild(metric);
        }
        const appearances = document.createElement('ul');
        appearances.className = 'ranking-appearances';
        for (const appearance of candidate.appearances) {
            const detail = document.createElement('li');
            const age = appearance.age == null ? 'âge inconnu' : `${appearance.age} ans`;
            detail.textContent = `${appearance.season} — ${age} — ${formatPlacement(appearance)}`;
            appearances.appendChild(detail);
        }
        item.append(heading, metrics, appearances);
        list.appendChild(item);
    }
    container.appendChild(list);
    const counts = d3.rollup(candidates, values => values.length, candidate => candidate.genre);
    const entries = [
        { label: 'Femmes', value: counts.get('F') || 0, color: GENDER_COLORS.F },
        { label: 'Hommes', value: counts.get('H') || 0, color: GENDER_COLORS.H }
    ];
    if (counts.get('unknown')) entries.push({ label: 'Non renseigné', value: counts.get('unknown'), color: '#999999' });
    renderPie(container, 'Répartition par genre du classement', entries);
}

function renderReturneeFlow() {
    const links = candidateStats.returnee_sankey.links;
    const maxReturns = d3.max(links, link => link.linked_returns);
    const stages = d3.range(maxReturns + 1).map(minimum => Object.fromEntries(
        ['F', 'H', 'unknown'].map(gender => [gender,
            d3.sum(links.filter(link => link.gender === gender && link.linked_returns >= minimum), link => link.candidates)])
    ));
    drawReturneeFlow(document.getElementById('returnee-flow'), stages);
}

function renderReturnees() {
    const container = document.getElementById('returnee-charts');
    const topThree = group => {
        const cutoff = group.length >= 3 ? group[2].retours : 0;
        return group.filter(candidate => candidate.retours >= cutoff);
    };
    const candidates = [...topThree(candidateStats.returnees.F), ...topThree(candidateStats.returnees.H)];
    const counts = [...new Set(candidates.map(candidate => candidate.participations.length))].sort((a, b) => b - a);
    for (const count of counts) {
        const group = document.createElement('section');
        group.className = 'returnee-group';
        const heading = document.createElement('h3');
        heading.textContent = `${count} saisons`;
        group.appendChild(heading);
        for (const candidate of candidates.filter(candidate => candidate.participations.length === count)
            .sort((a, b) => a.nom.localeCompare(b.nom, 'fr'))) {
            const card = document.createElement('article');
            card.className = 'returnee-card';
            const name = document.createElement('h4');
            name.textContent = candidate.nom;
            const appearances = document.createElement('p');
            const italic = document.createElement('em');
            italic.textContent = candidate.participations.map(participation =>
                `${participation.saison} (${formatPlacement({ ...participation, aban: false })})${participation.aban ? ' (abandon)' : ''}`
            ).join(', ');
            appearances.appendChild(italic);
            card.append(name, appearances);
            group.appendChild(card);
        }
        container.appendChild(group);
    }
    if (!counts.length) container.textContent = 'Aucun retour identifié.';
}

function drawReturneeFlow(container, stages) {
    const card = chartCard(container, 'Retours identifiés par genre');
    const width = Math.max(700, stages.length * 150), left = 110, right = 80;
    const x = d3.scalePoint().domain(d3.range(stages.length)).range([left, width - right]);
    const genders = [['F', 'Femmes'], ['H', 'Hommes']];
    if (stages[0].unknown) genders.push(['unknown', 'Non renseigné']);
    const height = 670, center = 330, maxBand = 135;
    const colors = { ...GENDER_COLORS, unknown: '#999999' };
    const scale = maxBand / Math.max(1, stages[0].F, stages[0].H + stages[0].unknown);
    const svg = d3.select(card).append('svg').attr('viewBox', `0 0 ${width} ${height}`)
        .attr('class', 'stats-svg').attr('role', 'img')
        .attr('aria-label', 'Flux des candidats par genre et nombre minimum de retours');
    stages.forEach((stage, index) => {
        svg.append('text').attr('x', x(index)).attr('y', 20).attr('text-anchor', 'middle')
            .text(index === 0 ? 'Tous' : `${index} retour${index > 1 ? 's' : ''} ou plus`);
    });
    const ribbon = (x1, y1, x2, y2, thickness) => {
        const mid = (x1 + x2) / 2;
        return `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2} L${x2},${y2 + thickness} C${mid},${y2 + thickness} ${mid},${y1 + thickness} ${x1},${y1 + thickness} Z`;
    };
    genders.forEach(([gender, label]) => {
        const labelY = gender === 'F' ? center - stages[0].F * scale / 2 :
            center + (gender === 'unknown' ? stages[0].H * scale : 0) + stages[0][gender] * scale / 2;
        svg.append('text').attr('x', 5).attr('y', labelY).attr('dominant-baseline', 'middle').text(label);
        for (let index = 0; index < stages.length; index++) {
            const count = stages[index][gender];
            const nodeHeight = count * scale;
            const y = gender === 'F' ? center - nodeHeight :
                center + (gender === 'unknown' ? stages[index].H * scale : 0);
            svg.append('rect').attr('x', x(index) - 6).attr('y', y).attr('width', 12)
                .attr('height', nodeHeight).attr('fill', colors[gender])
                .append('title').text(`${label} : ${count}`);
            if (index + 1 === stages.length) continue;
            const continuing = stages[index + 1][gender];
            const stopped = count - continuing;
            const nextY = gender === 'F' ? center - continuing * scale :
                center + (gender === 'unknown' ? stages[index + 1].H * scale : 0);
            if (continuing) {
                const sourceY = gender === 'F' ? center - continuing * scale : y;
                svg.append('path').attr('d', ribbon(x(index) + 6, sourceY, x(index + 1) - 6, nextY, continuing * scale))
                    .attr('fill', colors[gender]).attr('opacity', 0.45)
                    .append('title').text(`${label} : ${continuing} avec au moins ${index + 1} retour(s)`);
            }
            if (stopped) {
                const exitY = gender === 'F' ? center - maxBand - 12 - stopped * scale :
                    center + maxBand + 12 + (gender === 'unknown' ?
                        (stages[index].H - stages[index + 1].H) * scale : 0);
                const sourceY = gender === 'F' ? y : y + continuing * scale;
                svg.append('path').attr('d', ribbon(x(index) + 6, sourceY, x(index + 1) - 6, exitY, stopped * scale))
                    .attr('fill', colors[gender]).attr('opacity', 0.16)
                    .append('title').text(`${label} : ${stopped} sans retour supplémentaire`);
                svg.append('rect').attr('x', x(index + 1) - 6).attr('y', exitY)
                    .attr('width', 12).attr('height', stopped * scale).attr('fill', colors[gender]).attr('opacity', 0.35)
                    .append('title').text(`${label} : ${stopped} sans retour supplémentaire`);
            }
        }
    });
    const table = document.createElement('table');
    table.className = 'data-table';
    const header = table.createTHead().insertRow();
    for (const label of ['Retours minimum', ...stages.map((_, index) => index === 0 ? 'Tous' : String(index))]) {
        const cell = document.createElement('th');
        cell.scope = 'col';
        cell.textContent = label;
        header.appendChild(cell);
    }
    const body = table.createTBody();
    genders.forEach(([gender, label]) => {
        const row = body.insertRow();
        const heading = document.createElement('th');
        heading.scope = 'row';
        heading.textContent = label;
        row.appendChild(heading);
        stages.forEach(stage => { row.insertCell().textContent = stage[gender]; });
    });
    card.appendChild(table);
    const note = document.createElement('p');
    note.className = 'chart-note';
    note.textContent = 'Sarcelle : femmes ; violet : hommes ; gris : genre non renseigné. Les flux pâles représentent les personnes sans retour supplémentaire. Seuls les retours reliés à une première participation sont comptés.';
    card.appendChild(note);
}

function formatPlacement(candidate) {
    const place = candidate.place == null ? 'classement inconnu' :
        `${candidate.place === 1 ? '🏅 1re' : `${candidate.place}e`} place${candidate.place === 1 ? ' (gagnant-e)' : ''}`;
    return `${place}${candidate.aban ? ' (abandon)' : ''}`;
}

function renderAllStarCharts() {
    const stats = candidateStats.allstars;
    const ages = document.getElementById('allstar-age-charts');
    const genderEntries = [
        { label: 'Femmes', value: stats.first_outs.gender.F, color: GENDER_COLORS.F },
        { label: 'Hommes', value: stats.first_outs.gender.H, color: GENDER_COLORS.H }
    ];
    if (stats.first_outs.gender.unknown) genderEntries.push({ label: 'Non renseigné', value: stats.first_outs.gender.unknown, color: '#999999' });
    const genderChart = document.createElement('div');
    genderChart.className = 'first-out-gender-chart';
    ages.appendChild(genderChart);
    renderPie(genderChart, 'Genre des premiers éliminés', genderEntries);
    for (const [gender, firstTitle, allTitle] of [
        ['F', 'Âges des premières éliminées', 'Âges de toutes les candidates'],
        ['H', 'Âges des premiers éliminés', 'Âges de tous les candidats hommes']
    ]) {
        const pair = document.createElement('div');
        pair.className = 'pie-comparison';
        ages.appendChild(pair);
        renderPie(pair, firstTitle, groupAges(stats.first_outs.ages[gender].counts));
        renderPie(pair, allTitle, groupAges(stats.ages[gender].counts));
    }
    renderGenderCharts(document.getElementById('allstar-gender-charts'),
        { ...stats.gender, overall: stats.gender_overall }, [
        { key: 'overall', title: 'Ensemble des candidats' },
        { key: 'orientation', title: 'Orientation' },
        { key: 'winners', title: 'Gagnants', names: {
            F: stats.winners.filter(candidate => candidate.genre === 'F'),
            H: stats.winners.filter(candidate => candidate.genre === 'H')
        } }
    ]);
    const finals = stats.finales;
    renderFinaleBars(document.getElementById('allstar-finale-charts'), 'Composition des finales', [
        { label: 'H / H', color: GENDER_COLORS.H, finals: finals.filter(f => f.candidates.every(c => c.genre === 'H')) },
        { label: 'F / F', color: GENDER_COLORS.F, finals: finals.filter(f => f.candidates.every(c => c.genre === 'F')) },
        { label: 'F / H', color: '#b67b22', finals: finals.filter(f => f.candidates.some(c => c.genre === 'F') && f.candidates.some(c => c.genre === 'H')) }
    ], finals.length);
}

function renderFinaleCharts() {
    const container = document.getElementById('finale-charts');
    const finals = candidateStats.finales;
    const mixed = finals.filter(finale => finale.candidates.some(c => c.genre === 'F') &&
        finale.candidates.some(c => c.genre === 'H'));
    const outcome = finale => {
        const winners = finale.candidates.filter(c => c.place === 1);
        return winners.length === 2 ? 'tie' : winners[0].genre;
    };
    const outcomeGroups = subset => [
        { label: 'Victoire féminine', color: GENDER_COLORS.F, finals: subset.filter(f => outcome(f) === 'F') },
        { label: 'Victoire masculine', color: GENDER_COLORS.H, finals: subset.filter(f => outcome(f) === 'H') },
        { label: 'Égalité', color: '#b67b22', finals: subset.filter(f => outcome(f) === 'tie') }
    ];
    const byGender = gender => finals.filter(finale => finale.candidates.every(c => c.genre === gender));
    renderFinaleBars(container, 'Composition des finales', [
        { label: 'H / H', color: GENDER_COLORS.H, finals: byGender('H') },
        { label: 'F / F', color: GENDER_COLORS.F, finals: byGender('F') },
        { label: 'F / H', color: '#b67b22', finals: mixed }
    ], finals.length);
    renderFinaleBars(container, 'Résultat des finales F / H', outcomeGroups(mixed), mixed.length);
    const comparable = mixed.filter(finale => finale.candidates.every(c => c.age !== null));
    const ageDifference = finale => finale.candidates.find(c => c.genre === 'F').age -
        finale.candidates.find(c => c.genre === 'H').age;
    const older = comparable.filter(finale => ageDifference(finale) > 0);
    const younger = comparable.filter(finale => ageDifference(finale) < 0);
    const note = document.createElement('p');
    note.className = 'chart-note finale-note';
    note.textContent = `Finales F / H selon l'âge : ${mixed.length - older.length - younger.length} finale(s) exclue(s) des deux graphiques suivants (âges égaux ou inconnus). Chaque graphique a son propre total.`;
    container.appendChild(note);
    renderFinaleBars(container, 'La femme est plus âgée', outcomeGroups(older), older.length);
    renderFinaleBars(container, 'La femme est plus jeune', outcomeGroups(younger), younger.length);
}

function renderFinaleBars(container, title, groups, total) {
    const card = chartCard(container, title);
    const subtitle = document.createElement('p');
    subtitle.className = 'chart-note';
    subtitle.textContent = total ? `${total} finale(s) — survolez ou sélectionnez une catégorie.` : 'Aucune finale dans ce groupe.';
    card.appendChild(subtitle);
    const details = document.createElement('div');
    details.className = 'finale-details';
    details.setAttribute('aria-live', 'polite');
    details.textContent = 'Les finalistes apparaîtront ici.';
    for (const group of groups) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'percentage-row';
        const percent = total ? group.finals.length / total * 100 : 0;
        const label = document.createElement('span');
        label.textContent = group.label;
        const track = document.createElement('span');
        track.className = 'percentage-track';
        const bar = document.createElement('span');
        bar.className = 'percentage-fill';
        bar.style.width = `${percent}%`;
        bar.style.backgroundColor = group.color;
        track.appendChild(bar);
        const count = document.createElement('span');
        count.textContent = `${percent.toFixed(1).replace('.', ',')} % (${group.finals.length})`;
        button.append(label, track, count);
        const show = () => {
            details.replaceChildren();
            const heading = document.createElement('strong');
            heading.textContent = group.label;
            details.appendChild(heading);
            if (!group.finals.length) {
                details.append(' — aucune finale.');
                return;
            }
            const list = document.createElement('ul');
            for (const finale of group.finals) {
                const item = document.createElement('li');
                item.textContent = `${finale.saison} : ${finale.candidates.map(c =>
                    `${c.place === 1 ? '🏅 ' : ''}${c.nom.trim()}${c.place === 1 ? ' (gagnant-e)' : ''}${c.age === null ? '' : ` (${c.age} ans)`}`
                ).join(' / ')}`;
                list.appendChild(item);
            }
            details.appendChild(list);
        };
        button.addEventListener('pointerenter', show);
        button.addEventListener('focus', show);
        button.addEventListener('click', show);
        card.appendChild(button);
    }
    card.appendChild(details);
}

function renderChoiceCharts() {
    const container = document.getElementById('choice-charts');
    for (const [key, title] of [
        ['orientation', "Éliminés à l'orientation"],
        ['third', 'Troisièmes au classement'],
        ['ambassadors', 'Éliminés aux ambassadeurs']
    ]) {
        const stats = candidateStats.eliminations[key];
        const entries = [
            { label: 'Femmes', value: stats.F, color: GENDER_COLORS.F },
            { label: 'Hommes', value: stats.H, color: GENDER_COLORS.H }
        ];
        if (stats.unknown) entries.push({ label: 'Non renseigné', value: stats.unknown, color: '#999999' });
        renderPie(container, title, entries);
    }
}

function groupAges(counts) {
    const groups = [
        { label: '18 à 25 ans', value: 0, color: '#0072B2' },
        { label: '26 à 35 ans', value: 0, color: '#E69F00' },
        { label: '36 à 45 ans', value: 0, color: '#009E73' },
        { label: '46 ans et plus', value: 0, color: '#CC79A7' }
    ];
    let under18 = 0;
    for (const [ageString, count] of Object.entries(counts)) {
        const age = Number(ageString);
        if (age < 18) under18 += count;
        else if (age <= 25) groups[0].value += count;
        else if (age <= 35) groups[1].value += count;
        else if (age <= 45) groups[2].value += count;
        else groups[3].value += count;
    }
    if (under18) groups.unshift({ label: 'Moins de 18 ans', value: under18, color: '#999999' });
    return groups;
}

function chartCard(container, title, className = 'gender-chart') {
    const card = document.createElement('div');
    card.className = className;
    const heading = document.createElement(className === 'pie-comparison-chart' ? 'h4' : 'h3');
    heading.textContent = title;
    card.appendChild(heading);
    container.appendChild(card);
    return card;
}

function renderAgeChart(container, title, stats, candidates) {
    const card = chartCard(container, title);
    const allAges = Object.keys(stats.all.counts).map(Number);
    if (!allAges.length) {
        card.append('Aucun âge disponible.');
        return;
    }
    const width = 660, height = 300, margin = { top: 20, right: 20, bottom: 45, left: 45 };
    const ages = d3.range(Math.floor(d3.min(allAges) / 3) * 3, d3.max(allAges) + 1, 3);
    const x = d3.scaleBand().domain(ages).range([margin.left, width - margin.right]).padding(0.1);
    const sumGroup = (counts, age) => d3.sum([age, age + 1, age + 2], value => counts[value] || 0);
    const y = d3.scaleLinear().domain([0, d3.max(ages, age => sumGroup(stats.all.counts, age))]).nice()
        .range([height - margin.bottom, margin.top]);
    const layout = document.createElement('div');
    layout.className = 'age-chart-layout';
    const graph = document.createElement('div');
    graph.className = 'age-chart-graph';
    const details = document.createElement('div');
    details.className = 'age-details';
    details.setAttribute('aria-live', 'polite');
    details.textContent = 'Survolez ou sélectionnez une tranche pour afficher les candidats.';
    layout.append(graph, details);
    card.appendChild(layout);
    const svg = d3.select(graph).append('svg').attr('viewBox', `0 0 ${width} ${height}`)
        .attr('class', 'stats-svg').attr('role', 'group').attr('aria-label', title);
    svg.append('g').attr('transform', `translate(0,${height - margin.bottom})`)
        .call(d3.axisBottom(x).tickFormat(age => `${age}–${age + 2}`));
    svg.append('g').attr('transform', `translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(5).tickFormat(d3.format('d')));
    svg.append('text').attr('x', width / 2).attr('y', height - 5).attr('text-anchor', 'middle').text('Âge');
    svg.append('text').attr('x', margin.left).attr('y', 12).text('Candidats');
    const data = ages.map(age => {
        const female = sumGroup(stats.F.counts, age);
        const male = sumGroup(stats.H.counts, age);
        return { age, F: female, H: male, unknown: sumGroup(stats.all.counts, age) - female - male };
    });
    const colors = { ...GENDER_COLORS, unknown: '#999999' };
    const keys = ['F', 'H'];
    if (data.some(row => row.unknown > 0)) keys.push('unknown');
    const stack = d3.stack().keys(keys)(data);
    for (const series of stack) {
        svg.append('g').attr('fill', colors[series.key]).selectAll('rect')
            .data(series).join('rect')
            .attr('x', segment => x(segment.data.age))
            .attr('y', segment => y(segment[1]))
            .attr('height', segment => y(segment[0]) - y(segment[1]))
            .attr('width', x.bandwidth())
            .append('title')
            .text(segment => `${segment.data.age}–${segment.data.age + 2} ans : ${segment.data[series.key]} ${series.key === 'F' ? 'femmes' : series.key === 'H' ? 'hommes' : 'genre non renseigné'}`);
    }
    let lockedAge = null;
    function showAge(age) {
        const matches = candidates.filter(candidate => Number(candidate.age) >= age && Number(candidate.age) <= age + 2);
        details.replaceChildren();
        const heading = document.createElement('strong');
        heading.textContent = `${age}–${age + 2} ans — ${matches.length} candidat${matches.length > 1 ? 's' : ''}`;
        details.appendChild(heading);
        const list = document.createElement('ul');
        for (const candidate of matches) {
            const item = document.createElement('li');
            item.textContent = `${candidate.nom} — ${candidate.saison} — ${formatPlacement(candidate)}`;
            list.appendChild(item);
        }
        details.appendChild(list);
    }
    function selectAge(age) {
        lockedAge = lockedAge === age ? null : age;
        hitAreas.attr('aria-pressed', row => row.age === lockedAge ? 'true' : 'false')
            .classed('selected', row => row.age === lockedAge);
        showAge(age);
    }
    const hitAreas = svg.append('g').selectAll('rect').data(data.filter(row => row.F + row.H + row.unknown > 0))
        .join('rect')
        .attr('x', row => x(row.age)).attr('y', margin.top)
        .attr('width', x.bandwidth()).attr('height', height - margin.bottom - margin.top)
        .attr('fill', 'transparent').attr('class', 'age-hit-area')
        .attr('tabindex', 0).attr('role', 'button').attr('aria-pressed', 'false')
        .attr('aria-label', row => `${row.age} à ${row.age + 2} ans : afficher les candidats`)
        .on('pointerenter focus', (event, row) => { if (lockedAge === null) showAge(row.age); })
        .on('click', (event, row) => selectAge(row.age))
        .on('keydown', function(event, row) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                selectAge(row.age);
            }
        });
    const legend = document.createElement('div');
    legend.className = 'stats-legend';
    for (const [key, label, color] of [['F', 'Femmes', GENDER_COLORS.F], ['H', 'Hommes', GENDER_COLORS.H]]) {
        const item = document.createElement('span');
        item.innerHTML = `<i style="background:${color}"></i>${label}`;
        legend.appendChild(item);
    }
    if (keys.includes('unknown')) {
        const item = document.createElement('span');
        item.innerHTML = '<i style="background:#999999"></i>Genre non renseigné';
        legend.appendChild(item);
    }
    card.appendChild(legend);
}

function renderAgeSummary(container) {
    const card = chartCard(container, 'Âges moyens');
    const table = document.createElement('table');
    table.className = 'data-table';
    const header = table.createTHead().insertRow();
    for (const label of ['Étape', 'Ensemble', 'Femmes', 'Hommes']) {
        const cell = document.createElement('th');
        cell.scope = 'col';
        cell.textContent = label;
        header.appendChild(cell);
    }
    const body = table.createTBody();
    for (const [group, label] of [['all', 'Tous les candidats'], ['orientation', "À l'orientation"]]) {
        const row = body.insertRow();
        const heading = document.createElement('th');
        heading.scope = 'row';
        heading.textContent = label;
        row.appendChild(heading);
        for (const gender of ['all', 'F', 'H']) {
            const stats = candidateStats.ages[group][gender];
            row.insertCell().textContent = `${stats.average === null ? 'non disponible' : `${stats.average.toFixed(1).replace('.', ',')} ans`} (n = ${stats.total})`;
        }
    }
    const scroll = document.createElement('div');
    scroll.className = 'chart-scroll';
    scroll.appendChild(table);
    card.appendChild(scroll);
}

function renderAgeRates(container) {
    const card = chartCard(container, "Accès à l'orientation par tranche d'âge");
    const all = candidateStats.age_candidates.all;
    const orientation = candidateStats.age_candidates.orientation;
    const bins = d3.rollup(all, rows => rows.length, candidate => Math.floor(candidate.age / 3) * 3);
    const reached = d3.rollup(orientation, rows => rows.length, candidate => Math.floor(candidate.age / 3) * 3);
    const data = [...bins].sort((a, b) => a[0] - b[0]).map(([age, total]) => ({
        age, total, reached: reached.get(age) || 0
    }));
    if (!data.length) {
        card.append('Aucun âge disponible.');
        return;
    }
    data.forEach(row => {
        row.ratio = row.reached / row.total;
        row.rank = 1 + data.filter(other => other.reached * row.total > row.reached * other.total).length;
    });
    const width = Math.max(760, data.length * 48 + 80), height = 480;
    const margin = { top: 160, right: 20, bottom: 60, left: 55 };
    const x = d3.scaleBand().domain(data.map(d => d.age)).range([margin.left, width - margin.right]).padding(0.2);
    const y = d3.scaleLinear().domain([0, 0.5]).range([height - margin.bottom, margin.top]);
    const scroll = document.createElement('div');
    scroll.className = 'chart-scroll';
    card.appendChild(scroll);
    const svg = d3.select(scroll).append('svg').attr('viewBox', `0 0 ${width} ${height}`)
        .attr('class', 'stats-svg').attr('role', 'img').attr('aria-label', "Taux d'accès à l'orientation par âge");
    svg.append('g').attr('transform', `translate(0,${height - margin.bottom})`)
        .call(d3.axisBottom(x).tickFormat(age => `${age}–${age + 2}`));
    svg.append('g').attr('transform', `translate(${margin.left},0)`)
        .call(d3.axisLeft(y).tickValues([0, 0.1, 0.2, 0.3, 0.4, 0.5]).tickFormat(d3.format('.0%')));
    svg.append('text').attr('x', width / 2).attr('y', height - 8).attr('text-anchor', 'middle').text('Âge');
    svg.selectAll('rect').data(data).join('rect').attr('x', d => x(d.age))
        .attr('y', d => y(Math.min(d.ratio, 0.5))).attr('width', x.bandwidth())
        .attr('height', d => y(0) - y(Math.min(d.ratio, 0.5))).attr('fill', '#0B3954')
        .attr('tabindex', 0).append('title')
        .text(d => `${d.age}–${d.age + 2} ans : ${d.reached}/${d.total} (${(100 * d.reached / d.total).toFixed(1)} %)`);
    const labels = { 1: '🏅 1re place', 2: '2e place', 3: '3e place' };
    svg.selectAll('.rate-label').data(data).join('text').attr('class', 'rate-label')
        .attr('transform', d => `translate(${x(d.age) + x.bandwidth() / 2},${y(Math.min(d.ratio, 0.5)) - 6}) rotate(-55)`)
        .attr('text-anchor', 'start')
        .text(d => `${(100 * d.ratio).toFixed(1).replace('.', ',')} %${labels[d.rank] ? ` — ${labels[d.rank]}` : ''}`);
    const note = document.createElement('p');
    note.className = 'chart-note';
    note.textContent = "Nombre de participations ayant atteint l'orientation divisé par le nombre de participations de la tranche. L'axe vertical s'arrête à 50 % ; les valeurs supérieures sont indiquées au-dessus de la barre.";
    card.appendChild(note);
}

function renderPie(container, title, entries, className = 'gender-chart') {
    const card = chartCard(container, title, className);
    const total = d3.sum(entries, entry => entry.value);
    if (!total) {
        card.append('Aucune donnée disponible.');
        return;
    }
    const svg = d3.select(card).append('svg').attr('viewBox', '-120 -120 240 240')
        .attr('class', 'pie-svg').attr('role', 'group').attr('aria-label', title);
    const arc = d3.arc().innerRadius(0).outerRadius(105);
    const hoverInfo = document.createElement('p');
    hoverInfo.className = 'pie-hover-info';
    hoverInfo.setAttribute('aria-live', 'polite');
    hoverInfo.textContent = 'Survolez ou sélectionnez un secteur.';
    const showSlice = slice => {
        hoverInfo.textContent = `${slice.data.label} : ${slice.data.value} (${(slice.data.value / total * 100).toFixed(1).replace('.', ',')} %)`;
    };
    svg.selectAll('path').data(d3.pie().sort(null).value(entry => entry.value)(entries))
        .join('path').attr('d', arc).attr('fill', slice => slice.data.color)
        .attr('stroke', '#fff').attr('class', 'pie-slice')
        .attr('tabindex', slice => slice.data.value ? 0 : null)
        .attr('aria-label', slice => `${slice.data.label} : ${slice.data.value} (${(slice.data.value / total * 100).toFixed(1).replace('.', ',')} %)`)
        .on('pointerenter focus click', (event, slice) => showSlice(slice))
        .append('title')
        .text(slice => `${slice.data.label} : ${slice.data.value} (${(slice.data.value / total * 100).toFixed(1)} %)`);
    card.appendChild(hoverInfo);
    const legend = document.createElement('div');
    legend.className = 'stats-legend';
    entries.forEach(entry => {
        const item = document.createElement('span');
        const percent = (entry.value / total * 100).toFixed(1).replace('.', ',');
        item.innerHTML = `<i style="background:${entry.color}"></i>${entry.label} : ${entry.value} (${percent} %)`;
        legend.appendChild(item);
    });
    card.appendChild(legend);
}

window.addEventListener('load', init);
