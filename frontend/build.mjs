import {build} from 'esbuild';
import {mkdir,copyFile,readFile} from 'node:fs/promises';
import {transformAsync} from '@babel/core';
import angularLinker from '@angular/compiler-cli/linker/babel';
await mkdir('dist',{recursive:true});
await build({entryPoints:['.compiled/main.js'],bundle:true,minify:true,format:'iife',target:'chrome120',outfile:'dist/app.js',legalComments:'eof',define:{ngDevMode:'false',ngJitMode:'false',ngI18nClosureMode:'false'},
  plugins:[{name:'angular-linker',setup(builder){
    builder.onLoad({filter:/node_modules\/@angular\/.*\.m?js$/},async({path})=>{
      const source=await readFile(path,'utf8');
      const result=await transformAsync(source,{filename:path,plugins:[angularLinker],configFile:false,babelrc:false});
      return {contents:result.code,loader:'js'};
    });
  }}]});
for (const name of ['index.html','styles.css']) await copyFile('src/'+name,'dist/'+name);
const licenses=[];
for(const pkg of ['@angular/core','@angular/common','@angular/forms','@angular/platform-browser','rxjs','tslib']){
  for(const name of ['LICENSE','LICENSE.txt']){try{licenses.push(pkg+'\n'+await readFile('node_modules/'+pkg+'/'+name,'utf8'));break;}catch{}}
}
const {writeFile}=await import('node:fs/promises');
await writeFile('dist/THIRD_PARTY_NOTICES.txt',licenses.join('\n\n--------------------\n\n'));
console.log('Built offline Angular desktop interface.');
