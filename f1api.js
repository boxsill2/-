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

// --- 추가된 라우터 ---

// 드라이버 목록 페이지
router.get('/drivers', async (req, res) => {
    try {
        const drivers = await readJSON(path.join(DATA_DIR, 'drivers.json'));
        res.render('drivers', { drivers: drivers || [], currentPage: 'drivers' });
    } catch (e) {
        res.status(500).render('drivers', { drivers: [], error: '드라이버 데이터를 불러오는 데 실패했습니다.', currentPage: 'drivers' });
    }
});

// 팀 목록 페이지
router.get('/teams', async (req, res) => {
    try {
        const teams = await readJSON(path.join(DATA_DIR, 'teams.json'));
        res.render('teams', { teams: teams || [], currentPage: 'teams' });
    } catch (e) {
        res.status(500).render('teams', { teams: [], error: '팀 데이터를 불러오는 데 실패했습니다.', currentPage: 'teams' });
    }
});

// 용어집 페이지
router.get('/glossary', async (req, res) => {
    try {
        // f1_terms.json은 DATA_DIR이 아닌 ROOT_DIR에 위치
        const terms = await readJSON(path.join(ROOT_DIR, 'f1_terms.json'));
        res.render('glossary', { terms: terms || [], currentPage: 'glossary' });
    } catch (e) {
        res.status(500).render('glossary', { terms: [], error: '용어 데이터를 불러오는 데 실패했습니다.', currentPage: 'glossary' });
    }
});

// --- 기존 코드 유지 ---

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
            currentPage: 'schedule' 
        });
    } catch (e) {
        console.error(e);
        res.status(500).render('race-tracker', { session_key, driverDirectory: {}, sessionInfo: null, error: '페이지 로드 중 오류 발생', currentPage: 'schedule' });
    }
});

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

// --- 서버 실행 ---
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