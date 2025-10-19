// f1api.js
const fs = require('fs');
const path = require('path');
const express = require('express');
const { spawn } = require('child_process');

const router = express.Router();
const ROOT_DIR = __dirname;
const PUBLIC_DIR = path.join(ROOT_DIR, 'public');
const DATA_DIR = path.join(PUBLIC_DIR, 'data');

async function readJSON(filePath) { try { return JSON.parse(fs.readFileSync(filePath, 'utf8')); } catch { return null; } }
function slugify(text) { return String(text || '').toLowerCase().trim().replace(/[^a-z0-9\s-]/g, '').replace(/\s+/g, '-'); }

// --- 라우팅 설정 ---
router.get('/', (req, res) => res.redirect('/schedule'));

router.get('/schedule', async (req, res) => {
    try {
        const schedule = await readJSON(path.join(DATA_DIR, 'schedule.json'));
        res.render('schedule', { year: new Date().getFullYear(), schedule: schedule || [], error: null, currentPage: 'schedule' });
    } catch (e) { res.render('schedule', { year: new Date().getFullYear(), schedule: [], error: '스케줄 데이터를 불러오지 못했습니다.', currentPage: 'schedule' }); }
});

// 드라이버 목록 페이지
router.get('/drivers', async (req, res) => {
    try {
        const drivers = await readJSON(path.join(DATA_DIR, 'drivers.json'));
        res.render('drivers', { drivers: drivers || [], currentPage: 'drivers', error: null, slugify });
    } catch (e) {
        res.status(500).render('drivers', { drivers: [], error: '드라이버 데이터를 불러오는 데 실패했습니다.', currentPage: 'drivers', slugify });
    }
});

// 드라이버 상세 페이지
router.get('/drivers/:driverId', async (req, res) => {
    try {
        const { driverId } = req.params;
        const drivers = await readJSON(path.join(DATA_DIR, 'drivers.json'));
        const driver = drivers.find(d => slugify(d.full_name) === driverId);

        if (!driver) {
            return res.status(404).render('driver-detail', { info: null, description: null, season: {}, career: {}, error: '드라이버 정보를 찾을 수 없습니다.', currentPage: 'drivers', slugify });
        }

        const driverDescriptions = await readJSON(path.join(DATA_DIR, 'driver_descriptions.json'));
        const description = driverDescriptions[driver.full_name] || '이 드라이버에 대한 추가 정보가 없습니다.';
        
        let driverStats = await readJSON(path.join(DATA_DIR, 'stats', `${slugify(driver.full_name)}.json`));
        
        const seasonStats = driverStats?.season || {};
        const careerStats = driverStats?.career || {};

        res.render('driver-detail', { 
            info: driver, 
            description, 
            season: seasonStats, 
            career: careerStats, 
            error: null, 
            currentPage: 'drivers',
            slugify
        });
    } catch (e) {
        console.error(e);
        res.status(500).render('driver-detail', { info: null, description: null, season: {}, career: {}, error: '드라이버 데이터를 불러오는 데 실패했습니다.', currentPage: 'drivers', slugify });
    }
});

// 팀 목록 페이지
router.get('/teams', async (req, res) => {
    try {
        const teams = await readJSON(path.join(DATA_DIR, 'teams.json'));
        res.render('teams', { teams: teams || [], currentPage: 'teams', error: null });
    } catch (e) {
        res.status(500).render('teams', { teams: [], error: '팀 데이터를 불러오는 데 실패했습니다.', currentPage: 'teams' });
    }
});

// 팀 상세 페이지
router.get('/teams/:teamId', async (req, res) => {
    try {
        const { teamId } = req.params;
        const teams = await readJSON(path.join(DATA_DIR, 'teams.json'));
        const team = teams.find(t => t.slug === teamId);

        if (!team) {
            return res.status(404).render('team-detail', { info: null, drivers: [], error: '팀 정보를 찾을 수 없습니다.', currentPage: 'teams', slugify });
        }
        
        const drivers = await readJSON(path.join(DATA_DIR, 'drivers.json'));
        const teamDrivers = drivers.filter(d => d.team_name === team.team_name);

        res.render('team-detail', { info: team, drivers: teamDrivers, error: null, currentPage: 'teams', slugify });
    } catch (e) {
        console.error(e);
        res.status(500).render('team-detail', { info: null, drivers: [], error: '팀 데이터를 불러오는 데 실패했습니다.', currentPage: 'teams', slugify });
    }
});


// 용어집 페이지
router.get('/glossary', async (req, res) => {
    try {
        const terms = await readJSON(path.join(ROOT_DIR, 'f1_terms.json'));
        res.render('glossary', { terms: terms || [], currentPage: 'glossary', error: null });
    } catch (e) {
        res.status(500).render('glossary', { terms: [], error: '용어 데이터를 불러오는 데 실패했습니다.', currentPage: 'glossary' });
    }
});

// 리플레이 페이지
router.get('/replays/:session_key', async (req, res) => {
    const { session_key } = req.params;
    try {
        const schedule = await readJSON(path.join(DATA_DIR, 'schedule.json'));
        const layouts = await readJSON(path.join(DATA_DIR, 'track_layouts.json'));
        const sessionInfo = schedule?.find(s => String(s.session_key) === session_key) || null;
        
        if (!sessionInfo) {
            return res.status(404).render('race-tracker', { error: '해당 세션 정보를 찾을 수 없습니다.' });
        }
        
        const circuitName = sessionInfo.circuit_short_name?.toLowerCase().replace(/\s+/g, '-');
        const layout = layouts?.find(l => l.circuit_short_name === circuitName);

        let trackImageUrl = null;
        if (circuitName) {
            const possibleExtensions = ['avif', 'png', 'webp', 'jpg', 'jpeg'];
            for (const ext of possibleExtensions) {
                const imageName = `${circuitName}.${ext}`;
                const imagePath = path.join(PUBLIC_DIR, 'images', 'tracks', imageName);
                if (fs.existsSync(imagePath)) {
                    trackImageUrl = `/images/tracks/${imageName}`;
                    break;
                }
            }
        }

        const [drivers, f1Teams] = await Promise.all([
            readJSON(path.join(DATA_DIR, 'drivers.json')),
            readJSON(path.join(ROOT_DIR, 'f1_team.json'))
        ]);
        const driverDirectory = {};
        if (drivers && f1Teams) {
            const teamInfoMap = f1Teams.reduce((acc, team) => { acc[team.name] = { color: team.teamColor }; return acc; }, {});
            drivers.forEach(d => { if (d.number) driverDirectory[d.number] = { full_name: d.full_name, team_colour: teamInfoMap[d.team_name]?.color || '#FFFFFF' }; });
        }
        
        const finalSessionInfo = { ...sessionInfo, trackImageUrl, layout };

        res.render('race-tracker', { 
            session_key, 
            driverDirectory, 
            sessionInfo: finalSessionInfo, 
            currentPage: 'schedule',
            error: null
        });
    } catch (e) {
        console.error(e);
        res.status(500).render('race-tracker', { session_key, driverDirectory: {}, sessionInfo: null, error: '페이지 로드 중 오류 발생', currentPage: 'schedule' });
    }
});

// API 라우트
router.get('/api/locations/:session_key/:startTime/:endTime', (req, res) => {
    const { session_key, startTime, endTime } = req.params;
    const scriptPath = path.join(ROOT_DIR, 'get_driver_locations.py');
    if (!fs.existsSync(scriptPath)) {
        return res.status(500).json({ error: 'get_driver_locations.py 스크립트를 찾을 수 없습니다.' });
    }
    const pythonProcess = spawn('python', ['-X', 'utf8', scriptPath, session_key, startTime, endTime]);
    let output = '';
    pythonProcess.stdout.setEncoding('utf8');
    pythonProcess.stdout.on('data', (data) => { output += data.toString(); });
    pythonProcess.stderr.on('data', (data) => { console.error(`[Python STDERR]: ${data.toString('utf8')}`); });
    pythonProcess.on('close', (code) => {
        if (code !== 0) return res.status(500).json({ error: '데이터 조회 중 서버 오류 발생' });
        try { res.json(JSON.parse(output)); } catch (e) { res.status(500).json({ error: '스크립트 결과 파싱 실패' }); }
    });
});

// --- 서버 실행 (개발 환경에서만) ---
if (require.main === module) {
    const app = express();
    app.set('view engine', 'ejs');
    app.set('views', path.join(__dirname, 'views'));
    app.use(express.static(path.join(__dirname, 'public')));
    app.use('/', router);
    const PORT = process.env.PORT || 8080;
    app.listen(PORT, () => console.log(`서버가 http://localhost:${PORT} 에서 시작되었습니다.`));
}

module.exports = router;

