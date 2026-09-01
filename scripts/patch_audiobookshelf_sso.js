const fs = require('fs');

const SERVER_FILE = '/app/server/Server.js';
let code = fs.readFileSync(SERVER_FILE, 'utf8');

// Replace auto-login block
const oldPattern = /router\.get\(\['\/', '\/login'\], async \(req, res, next\) => \{[\s\S]*?next\(\);\s*\}\)/;

const newBlock = `router.get(['/', '/login'], async (req, res, next) => {
        const cfEmail = req.headers['cf-access-authenticated-user-email'] || req.headers['remote-email'] || req.headers['x-forwarded-email'];
        if (cfEmail && cfEmail.trim() && !req.query.accessToken) {
          const email = cfEmail.trim().toLowerCase();
          try {
            const Database = require('./Database');
            let user = null;
            if (email === 'david@davidmagnus.co.uk' || email === 'dave') {
              user = await Database.userModel.findOne({ where: { type: 'root' } });
            } else {
              user = await Database.userModel.findOne({ where: { email } });
              if (!user) {
                const username = email.split('@')[0];
                user = await Database.userModel.create({
                  username,
                  email,
                  type: 'user',
                  isActive: true,
                  permissions: {
                    download: true,
                    update: false,
                    delete: false,
                    upload: false,
                    createEreader: false,
                    accessAllLibraries: true,
                    accessAllTags: true,
                    accessExplicitContent: true,
                    selectedTagsNotAccessible: false,
                    librariesAccessible: [],
                    itemTagsSelected: []
                  }
                });
              }
            }
            if (user) {
              req.user = user;
              const userResponse = await this.auth.handleLoginSuccess(req, res, false);
              return res.redirect(302, \`/login?accessToken=\${userResponse.user.accessToken}\`);
            }
          } catch(err) {
            Logger.error(\`[Cloudflare-SSO AutoLogin] Error: \${err}\`);
          }
        }
        next();
      })`;

if (oldPattern.test(code)) {
  code = code.replace(oldPattern, newBlock);
  fs.writeFileSync(SERVER_FILE, code, 'utf8');
  console.log('Audiobookshelf Server.js auto-login updated to /login?accessToken=...');
} else {
  console.log('Old pattern not matched in Server.js');
}
