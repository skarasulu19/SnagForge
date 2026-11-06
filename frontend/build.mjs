import {build} from 'esbuild';
import {mkdir,copyFile,readFile} from 'node:fs/promises';
import {transformAsync} from '@babel/core';
import angularLinker from '@angular/compiler-cli/linker/babel';
await mkdir('dist',{recursive:true});
await build({entryPoints:['.compiled/main.js'],bundle:true,minify:true,format:'iife',target:'chrome120',outfile:'dist/app.js',legalComments:'eof',
  plugins:[{name:'angular-linker',setup(builder){
    builder.onLoad({filter:/node_modules\/@angular\/.*\.m?js$/},async({path})=>{
      const source=await readFile(path,'utf8');
      const result=await transformAsync(source,{filename:path,plugins:[angularLinker],configFile:false,babelrc:false});
      return {contents:result.code,loader:'js'};
    });
  }}]});
for (const name of ['index.html','styles.css']) await copyFile('src/'+name,'dist/'+name);
console.log('Built offline Angular desktop interface.');
