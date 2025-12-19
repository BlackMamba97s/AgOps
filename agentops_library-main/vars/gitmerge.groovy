import groovy.json.JsonSlurper

def gitMerge(gitUrl, appVersion, targetBranch){
	dir(contextDir){
		script{	
			withCredentials([usernamePassword(credentialsId: "JENKINS-A016998-CREDENTIAL", usernameVariable: 'gitUser', passwordVariable: 'gitPass')]) {

				git url: "${gitUrl}",
                    credentialsId: "JENKINS-A016998-CREDENTIAL"
				def encodedGitPass = URLEncoder.encode(gitPass, "UTF-8")
                def encodedAppVersion = URLEncoder.encode(appVersion, "UTF-8")
                def gitUrlMerge = gitUrl.replaceAll('https://', "https://${gitUser}:${encodedGitPass}@").replaceAll("\\r|\\n", "")

				sh """ git config user.email "${gitUser}@pipeline.com" """
				sh """ git config user.name "${gitUser}" """	

				sh """
					echo "Git clone su branch ${GIT_SOURCE}"
					git checkout tags/V${appVersion} -b branch-V${appVersion}
					git checkout master
					git branch --contains tags/V${appVersion}
					tagInMaster=\$(git branch --contains tags/V${appVersion} | grep "master" | wc -l)
					if [ \$tagInMaster -eq 0 ]; then
						echo "Tag NON trovato su branch master. Allineo il branch master"
						git merge branch-V${appVersion}
						git push ${gitUrlMerge} master 1>/dev/null 2>/dev/null  
					else
						echo "Tag trovato su banch master. Non aggiorno il branch"
					fi
				"""
				}
			}
	}	
}
return this