import type { ForgeConfig } from '@electron-forge/shared-types';
import { MakerDMG } from '@electron-forge/maker-dmg';
import * as path from 'path';
import { execSync } from 'child_process';

const config: ForgeConfig = {
    packagerConfig: {
        name: 'ClonEpub',
        appBundleId: 'com.jarodise.clonepub',
        icon: './assets/icon',
        // macOS signing - uncomment when you have Apple Developer credentials
        // osxSign: {},
        // osxNotarize: {
        //     appleId: process.env.APPLE_ID!,
        //     appleIdPassword: process.env.APPLE_ID_PASSWORD!,
        //     teamId: process.env.APPLE_TEAM_ID!
        // },
        extraResource: [
            // Python app source
            '../clonepub',
            '../pyproject.toml',
            '../uv.lock',
            '../README.md',
            // Bundled uv binary
            './assets/uv'
        ],
        // Ignore dev files when packaging
        ignore: [
            /^\/src/,
            /^\/\.git/,
            /^\/testing/,
            /\.ts$/,
            /tsconfig\.json$/
        ]
    },
    rebuildConfig: {},
    hooks: {
        postPackage: async (forgeConfig, options) => {
            const appPath = path.join(options.outputPaths[0], 'ClonEpub.app');
            console.log(`Ad-hoc signing ${appPath}...`);
            execSync(`codesign --force --deep -s - "${appPath}"`);
        }
    },
    makers: [
        new MakerDMG({
            name: 'ClonEpub',
            icon: './assets/icon.icns',
            background: './assets/dmg-background.png',
            format: 'ULFO',
            // @ts-ignore - 'path' is optional for 'file' type when it's the app itself
            contents: [
                { x: 190, y: 200, type: 'file', path: process.cwd() + '/out/ClonEpub-darwin-arm64/ClonEpub.app' },
                { x: 410, y: 200, type: 'link', path: '/Applications' }
            ],
            additionalDMGOptions: {
                window: {
                    size: { width: 600, height: 400 }
                }
            }
        })
    ]
};

export default config;
